import numpy as np
from gnuradio import gr
import pmt

class manual_ping_generator(gr.basic_block):
    def __init__(self, samp_rate=6e6, zc_seq=np.array([1, 1]),packet_len = 1024):
        gr.basic_block.__init__(self, name="Manual Ping Generator", 
                               in_sig=[np.complex64], out_sig=[np.complex64])
        self.seq = zc_seq
        self.samp_rate = samp_rate
        
        # 1. 接收 QT GUI 按鈕的觸發訊號
        self.message_port_register_in(pmt.intern("trig_in"))
        self.set_msg_handler(pmt.intern("trig_in"), self.handle_trigger)
        
        # 2. 建立一個廣播發射時間的訊息埠
        self.message_port_register_out(pmt.intern("tx_time_out"))
        
        self.pending_pings = 0
        self.last_tx_time = 0
        #
        # self.burst_data = np.concatenate((self.seq,zc_seq))
        # self.burst_data = np.concatenate((self.burst_data, zc_seq))
        # self.burst_data = np.concatenate((self.burst_data, zc_seq))

        # 準備對齊的 Burst Buffer (用 0 填充，確保 USB 傳輸穩定)
        target_length = packet_len
        pad_len = target_length - len(zc_seq)
        if pad_len < 0: pad_len = 0
        self.burst_data = np.concatenate((self.seq, np.zeros(pad_len, dtype=np.complex64)))
        self.burst_len = target_length
        self.set_min_noutput_items(self.burst_len)

    def handle_trigger(self, msg):
        self.pending_pings += 100

    def general_work(self, input_items, output_items):
        out = output_items[0]
        in_rx = input_items[0]
        n_output = len(out)
        n_input = len(in_rx)
        self.produce(0, 0) 

        # 1. 從輸入端 (RX) 攔截硬體真實時間
        tags = self.get_tags_in_window(0, 0, n_input)
        for tag in tags:
            if pmt.symbol_to_string(tag.key) == "rx_time":
                sec = pmt.to_uint64(pmt.tuple_ref(tag.value, 0))
                frac = pmt.to_double(pmt.tuple_ref(tag.value, 1))
                self.current_usrp_time = sec + frac
                self.last_rx_tag_offset = tag.offset

        # 如果還沒抓到 USRP 時間，先不要動作
        if not hasattr(self, 'current_usrp_time'):
            self.consume(0, n_input)
            return gr.WORK_CALLED_PRODUCE

        # 計算當下這個瞬間，USRP 的精確時間
        current_offset = self.nitems_read(0)
        diff_samples = current_offset - self.last_rx_tag_offset
        now_time_secs = self.current_usrp_time + (diff_samples / self.samp_rate)

        # 2. 沒按鈕時不送任何訊號
        if self.pending_pings <= 0:
            self.consume(0, n_input)
            return gr.WORK_CALLED_PRODUCE

        # Delay 0.5 sec to transmit signal
        tx_time_secs = now_time_secs + 0.5
        # 3. 🔴 按鈕觸發：基於「真實硬體時間」排程未來發射
        if self.pending_pings > 0 and n_output >= self.burst_len and now_time_secs - self.last_tx_time > 0.1:
            self.last_tx_time = tx_time_secs
            sec = int(tx_time_secs)
            frac = float(tx_time_secs - sec)
            time_pmt = pmt.make_tuple(pmt.from_uint64(sec), pmt.from_double(frac))
            
            # 注意：這裡的標籤位置依然要貼在輸出的邊界上
            out_offset = self.nitems_written(0)
            self.add_item_tag(0, out_offset, pmt.intern("tx_time"), time_pmt, pmt.intern("ping"))
            self.add_item_tag(0, out_offset, pmt.intern("tx_sob"), pmt.PMT_T, pmt.intern("ping"))
            self.add_item_tag(0, out_offset + self.burst_len - 1, pmt.intern("tx_eob"), pmt.PMT_T, pmt.intern("ping"))
            
            # 將真實的 ZC 訊號送進去
            out[:self.burst_len] = self.burst_data
            
            # 將排程時間告訴 RX 計算機
            self.message_port_pub(pmt.intern("tx_time_out"), time_pmt)
            # print(f"\n[TX] 🔴 排程突發 (Burst)！硬體預定發射時間: {tx_time_secs:.6f} s")
            
            self.pending_pings -= 1
            self.consume(0, n_input)
            self.produce(0, self.burst_len)
            return gr.WORK_CALLED_PRODUCE
            
        self.consume(0, n_input)
        return gr.WORK_CALLED_PRODUCE
