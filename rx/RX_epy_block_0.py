import numpy as np
from gnuradio import gr
import pmt
import  packet_utils


class rtt_responder_advanced(gr.basic_block):
    def __init__(
        self,
        zc_seq=np.array([1, 1]),
        samp_rate=1e6,
        delay_secs=0.5,
        zc_length=839,
        k_peak2noise=8,
        fixed_threshold=200,
    ):
        gr.basic_block.__init__(
            self,
            name="RTT Responder Advanced",
            in_sig=[np.complex64],
            out_sig=[np.complex64],
        )
        self.responder_id = 0x02  # Unique ID for this responder
        self.zc_seq = zc_seq
        self.samp_rate = samp_rate
        self.delay = delay_secs
        self.zc_length = zc_length
        self.k_peak2noise = k_peak2noise
        self.fixed_threshold = fixed_threshold
        self.transmit_num = 0
        self.measurement_number = 0

        self.last_rx_time = None
        self.last_tag_offset = 0

        self.cooldown_secs = 0.001  # Wait 50 ms before sending again
        self.cooldown_samples = int(self.cooldown_secs * self.samp_rate)

        # Do not allow a reply too close to the start of the stream.
        self.next_allowed_tx_offset = int(0.01 * self.samp_rate)

        # BPSK settings
        self.sps = 60  # Samples per symbol
        # The total sequence length must accommodate ZC + gap + payload
        self.n_bits = packet_utils.RESPONSE_PACKET_BITS
        self.seq_len = zc_length + 100 + self.sps * self.n_bits  # ZC + gap + payload
        # Set the out buffer minimum output buffer size to seq_len to ensure we can always produce a full burst
        self.set_min_output_buffer(0, self.seq_len+1000)  # Add some extra margin
        self.burst_data = np.zeros(self.seq_len, dtype=np.complex64)

        self.burst_active = False
        self.burst_pos = 0
        self.burst_total_len = 0
        self.pending_tx_time = None
    def general_work(self, input_items, output_items):
        in_sig = input_items[0]
        out = output_items[0]

        n_input = len(in_sig)

        # 憒?銝???瘝?嚗?蝥嚗??菜葫??peak
        if self.burst_active:
            to_produce = self.output_burst_chunk(out)

            self.consume(0, n_input)
            self.produce(0, to_produce)
            return gr.WORK_CALLED_PRODUCE

        mag = np.abs(in_sig)
        abs_start = self.nitems_read(0)

        tags = self.get_tags_in_window(0, 0, n_input)
        for tag in tags:
            if pmt.symbol_to_string(tag.key) == "rx_time":
                self.last_rx_time = tag.value
                self.last_tag_offset = int(tag.offset)

        peak_indices = self.find_peak_indices(mag)

        if peak_indices is None:
            self.consume(0, n_input)
            return gr.WORK_CALLED_PRODUCE

        peak_local = int(peak_indices)
        current_peak_offset = int(abs_start + peak_local)

        if self.last_rx_time is None:
            print("[WARN] No rx_time tag available yet. Cannot timestamp T2.")
            self.consume(0, n_input)
            return gr.WORK_CALLED_PRODUCE

        rx_base_tick = int(packet_utils.pmt_time_to_ticks(self, self.last_rx_time))
        diff_samples = int(current_peak_offset - self.last_tag_offset)

        t2_correction_samples = int(getattr(self, "t2_correction_samples", 0))
        t2_tick = int(rx_base_tick + diff_samples + t2_correction_samples - self.zc_length)

        delay_samples = int(round(self.delay * self.samp_rate))
        t3_tick = int(t2_tick + delay_samples)

        tx_target_time = packet_utils.ticks_to_pmt_time(self, t3_tick)

        if current_peak_offset < self.next_allowed_tx_offset:
            self.consume(0, n_input)
            return gr.WORK_CALLED_PRODUCE

        ts_mask = (1 << packet_utils.T2_MINUS_T3_BITS) - 1
        measurement_mask = (1 << packet_utils.MEASUREMENT_NUMBER_BITS) - 1

        t2_minus_t3_payload = int((t2_tick - t3_tick) & ts_mask)
        self.measurement_number = (self.measurement_number + 1) & measurement_mask

        packet_bits = packet_utils.build_response_packet(
            responder_id=int(self.responder_id),
            t2_minus_t3=t2_minus_t3_payload,
            measurement_number=self.measurement_number,
        )

        bpsk_samples = self.generate_bpsk(packet_bits, self.sps)
        gap = np.zeros(100, dtype=np.complex64)

        tail_guard = np.zeros(100, dtype=np.complex64)

        self.burst_data = np.concatenate((
            np.asarray(self.zc_seq, dtype=np.complex64),
            gap,
            np.asarray(bpsk_samples, dtype=np.complex64),
            tail_guard,
        )).astype(np.complex64)

        self.burst_total_len = len(self.burst_data)
        self.burst_pos = 0
        self.burst_active = True
        self.pending_tx_time = tx_target_time

        self.next_allowed_tx_offset = current_peak_offset + self.cooldown_samples

        to_produce = self.output_burst_chunk(out)

        self.consume(0, n_input)
        self.produce(0, to_produce)
        return gr.WORK_CALLED_PRODUCE

    def generate_bpsk(self, bits, sps):
        symbols = [(-0.7 + 0j) if int(b) else (0.7 + 0j) for b in bits]
        sym_array = np.asarray(symbols, dtype=np.complex64)
        return np.repeat(sym_array, sps)

    def find_peak_indices(self, in_sig):
        magnitude = in_sig
        noise_floor = np.mean(magnitude)
        threshold = max(noise_floor * self.k_peak2noise, self.fixed_threshold)

        candidate_indices = np.where(magnitude > threshold)[0]

        if candidate_indices.size == 0:
            return None
        
        peak_indices = candidate_indices[np.argmax(magnitude[candidate_indices])]

        return peak_indices

    def add_time(self, time_tuple, offset_secs):
        secs = pmt.to_uint64(pmt.tuple_ref(time_tuple, 0))
        frac = pmt.to_double(pmt.tuple_ref(time_tuple, 1))

        new_frac = frac + offset_secs
        full_secs = secs + int(new_frac)
        remainder_frac = new_frac % 1.0
        return pmt.make_tuple(pmt.from_uint64(full_secs), pmt.from_double(remainder_frac))

    def issue_burst(self, out_buffer, tx_time):
        self.add_item_tag(
            0, self.nitems_written(0), pmt.intern("tx_time"), tx_time, pmt.intern("resp")
        )
        self.add_item_tag(
            0, self.nitems_written(0), pmt.intern("tx_sob"), pmt.PMT_T, pmt.intern("resp")
        )
        self.add_item_tag(
            0,
            self.nitems_written(0) + self.seq_len - 1,
            pmt.intern("tx_eob"),
            pmt.PMT_T,
            pmt.intern("resp"),
        )
        out_buffer[: self.seq_len] = self.burst_data[0:self.seq_len]

    def output_burst_chunk(self, out_buffer):
        n_output = len(out_buffer)

        remaining = self.burst_total_len - self.burst_pos
        to_copy = min(remaining, n_output)

        start = self.burst_pos
        end = start + to_copy

        out_buffer[:to_copy] = self.burst_data[start:end]

        abs_out_start = self.nitems_written(0)

        # 蝚砌?畾菜???tx_time ??tx_sob
        if start == 0:
            self.transmit_num = self.transmit_num +1
            print("TX",self.transmit_num )
            self.add_item_tag(
                0,
                abs_out_start,
                pmt.intern("tx_time"),
                self.pending_tx_time,
                pmt.intern("resp"),
            )
            self.add_item_tag(
                0,
                abs_out_start,
                pmt.intern("tx_sob"),
                pmt.PMT_T,
                pmt.intern("resp"),
            )

        self.burst_pos = end

        # ?敺?畾菜???tx_eob
        if self.burst_pos >= self.burst_total_len:
            self.add_item_tag(
                0,
                abs_out_start + to_copy - 1,
                pmt.intern("tx_eob"),
                pmt.PMT_T,
                pmt.intern("resp"),
            )

            self.burst_active = False
            self.burst_pos = 0
            self.burst_total_len = 0
            self.pending_tx_time = None

        return to_copy
