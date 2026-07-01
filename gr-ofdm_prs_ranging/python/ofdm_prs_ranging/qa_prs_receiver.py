#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 GNU Radio ZC TWR contributors.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

import os
import tempfile
import time

import numpy
import pmt
from gnuradio import blocks, gr, gr_unittest

try:
    from gnuradio import ofdm_prs_ranging
except ImportError:
    import sys

    dirname, filename = os.path.split(os.path.abspath(__file__))
    sys.path.append(os.path.join(dirname, "bindings"))
    from gnuradio import ofdm_prs_ranging


class qa_prs_receiver(gr_unittest.TestCase):
    def setUp(self):
        self.tb = gr.top_block()

    def tearDown(self):
        self.tb = None

    def test_clean_frame_pipeline_outputs_measurement(self):
        tx = ofdm_prs_ranging.prs_timed_burst_source(attach_tx_time=False)
        frame = list(tx.frame_samples())
        prefix = [0j] * 300
        data = prefix + frame + [0j] * 300
        timing = blocks.vector_source_c(data, False)

        detector = ofdm_prs_ranging.prs_frame_detector(threshold=0.30)
        fft = ofdm_prs_ranging.prs_fft_receiver()
        channel = ofdm_prs_ranging.prs_channel_estimator()
        phase = ofdm_prs_ranging.prs_phase_slope_estimator(max_residual_rms=1.0)
        debug = blocks.message_debug()

        self.tb.connect(timing, detector)
        self.tb.msg_connect((detector, "frame_out"), (fft, "frame_in"))
        self.tb.msg_connect((fft, "symbols_out"), (channel, "symbols_in"))
        self.tb.msg_connect((channel, "channel_out"), (phase, "channel_in"))
        self.tb.msg_connect((phase, "measurement_out"), (debug, "store"))
        self.tb.run()

        self.assertGreaterEqual(debug.num_messages(), 1)
        msg = debug.get_message(0)
        meta = pmt.car(msg)
        self.assertEqual(pmt.to_uint64(pmt.dict_ref(meta, pmt.intern("recv_id"), pmt.PMT_NIL)), 0)
        self.assertEqual(pmt.to_uint64(pmt.dict_ref(meta, pmt.intern("frame_id"), pmt.PMT_NIL)), 0)
        self.assertTrue(pmt.to_bool(pmt.dict_ref(meta, pmt.intern("frame_id_valid"), pmt.PMT_F)))
        self.assertEqual(pmt.to_uint64(pmt.dict_ref(meta, pmt.intern("frame_start"), pmt.PMT_NIL)), 300)
        self.assertLess(abs(pmt.to_double(pmt.dict_ref(meta, pmt.intern("fine_delay_samples"), pmt.PMT_NIL))), 0.25)
        self.assertGreater(pmt.to_double(pmt.dict_ref(meta, pmt.intern("peak_metric"), pmt.PMT_NIL)), 0.9)
        self.assertTrue(pmt.to_bool(pmt.dict_ref(meta, pmt.intern("valid"), pmt.PMT_F)))

    def test_csv_logger_writes_measurement_row(self):
        fd, path = tempfile.mkstemp(prefix="prs_meas_", suffix=".csv")
        os.close(fd)
        try:
            logger = ofdm_prs_ranging.prs_csv_logger(path, False)
            meta = pmt.make_dict()
            for key, value in (
                ("recv_id", pmt.from_uint64(3)),
                ("frame_id", pmt.from_uint64(7)),
                ("frame_id_valid", pmt.PMT_T),
                ("coarse_delay", pmt.from_double(1.0e-6)),
                ("fine_delay", pmt.from_double(2.0e-9)),
                ("cfo", pmt.from_double(0.0)),
                ("snr", pmt.from_double(30.0)),
                ("phase_residual", pmt.from_double(0.01)),
                ("peak_metric", pmt.from_double(0.95)),
                ("payload_metric", pmt.from_double(0.98)),
                ("quality", pmt.from_double(0.9)),
            ):
                meta = pmt.dict_add(meta, pmt.intern(key), value)
            strobe = blocks.message_strobe(pmt.cons(meta, pmt.PMT_NIL), 50)
            self.tb.msg_connect((strobe, "strobe"), (logger, "measurement_in"))
            self.tb.start()
            time.sleep(0.12)
            self.tb.stop()
            self.tb.wait()

            with open(path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines()]
            self.assertEqual(lines[0], "recv_id,frame_id,frame_id_valid,coarse_delay,fine_delay,cfo,snr,phase_residual,peak_metric,payload_metric,quality")
            self.assertTrue(lines[1].startswith("3,7,1,"))
        finally:
            if os.path.exists(path):
                os.unlink(path)


if __name__ == "__main__":
    gr_unittest.run(qa_prs_receiver)
