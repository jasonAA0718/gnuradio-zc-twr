#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: ZC_TX
# GNU Radio version: 3.10.11.0

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import blocks
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import uhd
import time
import numpy as np
import sip
import threading
import tx_epy_block_0 as epy_block_0  # embedded python block
import tx_epy_block_0_0_0 as epy_block_0_0_0  # embedded python block



class tx(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "ZC_TX", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("ZC_TX")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "tx")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.zc_length = zc_length = 1399
        self.zc_seq_31 = zc_seq_31 = np.exp(-1j * np.pi * int(31) * np.arange(zc_length) * (np.arange(zc_length) + 1) / zc_length).astype(np.complex64)
        self.zc_seq_25 = zc_seq_25 = np.exp(-1j * np.pi * int(25)* np.arange(zc_length) * (np.arange(zc_length) + 1) / zc_length).astype(np.complex64)
        self.samp_rate = samp_rate = 10e6
        self.packet_len = packet_len = 2048*2
        self.gain = gain = 1
        self.freq = freq = 1400e6

        ##################################################
        # Blocks
        ##################################################

        self._gain_range = qtgui.Range(0, 1, 0.05, 1, 200)
        self._gain_win = qtgui.RangeWidget(self._gain_range, self.set_gain, "'gain'", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._gain_win)
        self.uhd_usrp_source_0 = uhd.usrp_source(
            ",".join(("serial=34D0563", "recv_buff_size=20000000,num_recv_frames=1500")),
            uhd.stream_args(
                cpu_format="fc32",
                args='',
                channels=list(range(0,1)),
            ),
        )
        self.uhd_usrp_source_0.set_subdev_spec('A:B', 0)
        self.uhd_usrp_source_0.set_samp_rate(samp_rate)
        self.uhd_usrp_source_0.set_time_unknown_pps(uhd.time_spec(0))

        self.uhd_usrp_source_0.set_center_freq(freq, 0)
        self.uhd_usrp_source_0.set_antenna("RX2", 0)
        self.uhd_usrp_source_0.set_bandwidth(samp_rate, 0)
        self.uhd_usrp_source_0.set_normalized_gain(1, 0)
        self.uhd_usrp_sink_0 = uhd.usrp_sink(
            ",".join(("serial=34D0563", '')),
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

        self.uhd_usrp_sink_0.set_center_freq(freq, 0)
        self.uhd_usrp_sink_0.set_antenna("TX/RX", 0)
        self.uhd_usrp_sink_0.set_bandwidth(samp_rate, 0)
        self.uhd_usrp_sink_0.set_normalized_gain(gain, 0)
        self.sent_ping = _sent_ping_toggle_button = qtgui.MsgPushButton('sent_ping', 'pressed',1,"default","default")
        self.sent_ping = _sent_ping_toggle_button

        self.top_layout.addWidget(_sent_ping_toggle_button)
        self.qtgui_time_sink_x_0_0_2 = qtgui.time_sink_f(
            1024, #size
            samp_rate, #samp_rate
            "RX Cov peak", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_time_sink_x_0_0_2.set_update_time(0.1)
        self.qtgui_time_sink_x_0_0_2.set_y_axis(0, 1000)

        self.qtgui_time_sink_x_0_0_2.set_y_label('Amplitude', "")

        self.qtgui_time_sink_x_0_0_2.enable_tags(True)
        self.qtgui_time_sink_x_0_0_2.set_trigger_mode(qtgui.TRIG_MODE_NORM, qtgui.TRIG_SLOPE_POS, 100, 0, 0, "")
        self.qtgui_time_sink_x_0_0_2.enable_autoscale(False)
        self.qtgui_time_sink_x_0_0_2.enable_grid(False)
        self.qtgui_time_sink_x_0_0_2.enable_axis_labels(True)
        self.qtgui_time_sink_x_0_0_2.enable_control_panel(False)
        self.qtgui_time_sink_x_0_0_2.enable_stem_plot(False)


        labels = ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_time_sink_x_0_0_2.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_time_sink_x_0_0_2.set_line_label(i, labels[i])
            self.qtgui_time_sink_x_0_0_2.set_line_width(i, widths[i])
            self.qtgui_time_sink_x_0_0_2.set_line_color(i, colors[i])
            self.qtgui_time_sink_x_0_0_2.set_line_style(i, styles[i])
            self.qtgui_time_sink_x_0_0_2.set_line_marker(i, markers[i])
            self.qtgui_time_sink_x_0_0_2.set_line_alpha(i, alphas[i])

        self._qtgui_time_sink_x_0_0_2_win = sip.wrapinstance(self.qtgui_time_sink_x_0_0_2.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._qtgui_time_sink_x_0_0_2_win)
        self.fft_filter_xxx_0_0 = filter.fft_filter_ccc(1, np.conj(zc_seq_31[::-1]), 1)
        self.fft_filter_xxx_0_0.declare_sample_delay(0)
        self.epy_block_0_0_0 = epy_block_0_0_0.manual_ping_generator(samp_rate=samp_rate, zc_seq=zc_seq_25, packet_len=packet_len)
        self.epy_block_0 = epy_block_0.rtt_calculator(samp_rate=samp_rate, zc_length=zc_length, delay_secs=0.005, k_peak2noise=27, fixed_threshold=100, distance_setting_m=22.5, log_path="/home/cnsl/Desktop/BPSK/log/rtt_measurements.csv")
        self.blocks_file_sink_0 = blocks.file_sink(gr.sizeof_gr_complex*1, '/home/cnsl/Desktop/BPSK/log/capture_iq.dat', False)
        self.blocks_file_sink_0.set_unbuffered(False)
        self.blocks_complex_to_mag_0_0 = blocks.complex_to_mag(1)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.epy_block_0_0_0, 'tx_time_out'), (self.epy_block_0, 'tx_time_in'))
        self.msg_connect((self.sent_ping, 'pressed'), (self.epy_block_0_0_0, 'trig_in'))
        self.connect((self.blocks_complex_to_mag_0_0, 0), (self.qtgui_time_sink_x_0_0_2, 0))
        self.connect((self.epy_block_0, 0), (self.blocks_file_sink_0, 0))
        self.connect((self.epy_block_0_0_0, 0), (self.uhd_usrp_sink_0, 0))
        self.connect((self.fft_filter_xxx_0_0, 0), (self.blocks_complex_to_mag_0_0, 0))
        self.connect((self.fft_filter_xxx_0_0, 0), (self.epy_block_0, 0))
        self.connect((self.uhd_usrp_source_0, 0), (self.epy_block_0, 1))
        self.connect((self.uhd_usrp_source_0, 0), (self.epy_block_0_0_0, 0))
        self.connect((self.uhd_usrp_source_0, 0), (self.fft_filter_xxx_0_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "tx")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_zc_length(self):
        return self.zc_length

    def set_zc_length(self, zc_length):
        self.zc_length = zc_length
        self.set_zc_seq_25(np.exp(-1j * np.pi * int(25)* np.arange(self.zc_length) * (np.arange(self.zc_length) + 1) / self.zc_length).astype(np.complex64))
        self.set_zc_seq_31(np.exp(-1j * np.pi * int(31) * np.arange(self.zc_length) * (np.arange(self.zc_length) + 1) / self.zc_length).astype(np.complex64))
        self.epy_block_0.zc_length = self.zc_length

    def get_zc_seq_31(self):
        return self.zc_seq_31

    def set_zc_seq_31(self, zc_seq_31):
        self.zc_seq_31 = zc_seq_31
        self.fft_filter_xxx_0_0.set_taps(np.conj(self.zc_seq_31[::-1]))

    def get_zc_seq_25(self):
        return self.zc_seq_25

    def set_zc_seq_25(self, zc_seq_25):
        self.zc_seq_25 = zc_seq_25

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.epy_block_0.samp_rate = self.samp_rate
        self.epy_block_0_0_0.samp_rate = self.samp_rate
        self.qtgui_time_sink_x_0_0_2.set_samp_rate(self.samp_rate)
        self.uhd_usrp_sink_0.set_samp_rate(self.samp_rate)
        self.uhd_usrp_sink_0.set_bandwidth(self.samp_rate, 0)
        self.uhd_usrp_source_0.set_samp_rate(self.samp_rate)
        self.uhd_usrp_source_0.set_bandwidth(self.samp_rate, 0)

    def get_packet_len(self):
        return self.packet_len

    def set_packet_len(self, packet_len):
        self.packet_len = packet_len

    def get_gain(self):
        return self.gain

    def set_gain(self, gain):
        self.gain = gain
        self.uhd_usrp_sink_0.set_normalized_gain(self.gain, 0)

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = freq
        self.uhd_usrp_sink_0.set_center_freq(self.freq, 0)
        self.uhd_usrp_source_0.set_center_freq(self.freq, 0)




def main(top_block_cls=tx, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
