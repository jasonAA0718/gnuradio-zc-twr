#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: PRS SS-RTT Responder 10M 1399
# Description: Minimal OFDM PRS SS-RTT responder at 10 MHz and 1399 MHz
# GNU Radio version: 3.10.11.0

from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import ofdm_prs_ranging
from gnuradio import uhd
import time
import threading




class prs_ssrtt_responder_10M_1399(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "PRS SS-RTT Responder 10M 1399", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 10e6
        self.reply_delay_samples = reply_delay_samples = 500000
        self.center_freq = center_freq = 1399e6

        ##################################################
        # Blocks
        ##################################################

        self.uhd_usrp_source_0_0 = uhd.usrp_source(
            ",".join(("serial=34D0564", "recv_buff_size=20000000,num_recv_frames=700")),
            uhd.stream_args(
                cpu_format="fc32",
                args='',
                channels=list(range(0,1)),
            ),
        )
        self.uhd_usrp_source_0_0.set_subdev_spec('A:B', 0)
        self.uhd_usrp_source_0_0.set_samp_rate(samp_rate)
        self.uhd_usrp_source_0_0.set_time_unknown_pps(uhd.time_spec(0))

        self.uhd_usrp_source_0_0.set_center_freq(center_freq, 0)
        self.uhd_usrp_source_0_0.set_antenna("RX2", 0)
        self.uhd_usrp_source_0_0.set_bandwidth(samp_rate, 0)
        self.uhd_usrp_source_0_0.set_normalized_gain(0.6, 0)
        self.uhd_usrp_sink_0 = uhd.usrp_sink(
            ",".join(("serial=34D0564", '')),
            uhd.stream_args(
                cpu_format="fc32",
                args='',
                channels=list(range(0,1)),
            ),
            "",
        )
        self.uhd_usrp_sink_0.set_subdev_spec('A:A', 0)
        self.uhd_usrp_sink_0.set_samp_rate(samp_rate)
        # No synchronization enforced.

        self.uhd_usrp_sink_0.set_center_freq(center_freq, 0)
        self.uhd_usrp_sink_0.set_antenna("TX/RX", 0)
        self.uhd_usrp_sink_0.set_bandwidth(samp_rate, 0)
        self.uhd_usrp_sink_0.set_normalized_gain(0.5, 0)
        self.prs_ssrtt_responder_0 = ofdm_prs_ranging.prs_ssrtt_responder(samp_rate, reply_delay_samples)
        self.prs_source = ofdm_prs_ranging.prs_timed_burst_source(
            samp_rate, 1024, 128, 600, 16,
            128, 16, 839,
            1000, 1000, 0.01,
            0.1, 0.2, 13990001, 1,
            True)
        self.prs_phase_slope_estimator_0 = ofdm_prs_ranging.prs_phase_slope_estimator(samp_rate, 1024, 600, 1.0)
        self.prs_frame_detector_0 = ofdm_prs_ranging.prs_frame_detector(samp_rate, 1024, 128, 600, 16, 128, 16, 839, 1000, 1000, 0.35, 10000)
        self.prs_fft_receiver_0 = ofdm_prs_ranging.prs_fft_receiver(samp_rate, 1024, 128, 600, 16)
        self.prs_channel_estimator_0 = ofdm_prs_ranging.prs_channel_estimator(samp_rate, 1024, 600, 16, 13990001)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.prs_channel_estimator_0, 'channel_out'), (self.prs_phase_slope_estimator_0, 'channel_in'))
        self.msg_connect((self.prs_fft_receiver_0, 'symbols_out'), (self.prs_channel_estimator_0, 'symbols_in'))
        self.msg_connect((self.prs_frame_detector_0, 'frame_out'), (self.prs_fft_receiver_0, 'frame_in'))
        self.msg_connect((self.prs_phase_slope_estimator_0, 'measurement_out'), (self.prs_ssrtt_responder_0, 'measurement_in'))
        self.msg_connect((self.prs_ssrtt_responder_0, 'trigger_out'), (self.prs_source, 'trigger'))
        self.connect((self.prs_source, 0), (self.uhd_usrp_sink_0, 0))
        self.connect((self.uhd_usrp_source_0_0, 0), (self.prs_frame_detector_0, 0))
        self.connect((self.uhd_usrp_source_0_0, 0), (self.prs_source, 0))


    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.uhd_usrp_sink_0.set_samp_rate(self.samp_rate)
        self.uhd_usrp_sink_0.set_bandwidth(self.samp_rate, 0)
        self.uhd_usrp_source_0_0.set_samp_rate(self.samp_rate)
        self.uhd_usrp_source_0_0.set_bandwidth(self.samp_rate, 0)

    def get_reply_delay_samples(self):
        return self.reply_delay_samples

    def set_reply_delay_samples(self, reply_delay_samples):
        self.reply_delay_samples = reply_delay_samples

    def get_center_freq(self):
        return self.center_freq

    def set_center_freq(self, center_freq):
        self.center_freq = center_freq
        self.uhd_usrp_sink_0.set_center_freq(self.center_freq, 0)
        self.uhd_usrp_source_0_0.set_center_freq(self.center_freq, 0)




def main(top_block_cls=prs_ssrtt_responder_10M_1399, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    tb.flowgraph_started.set()

    try:
        input('Press Enter to quit: ')
    except EOFError:
        pass
    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
