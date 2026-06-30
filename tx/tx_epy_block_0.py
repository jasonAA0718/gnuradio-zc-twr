import csv
import os
from datetime import datetime, timezone

import numpy as np
from gnuradio import gr
import pmt
import packet_utils


class rtt_calculator(gr.basic_block):
    def __init__(
        self,
        samp_rate=6e6,
        zc_length=839,
        delay_secs=0.5,
        k_peak2noise=17,
        fixed_threshold=200,
        distance_setting_m=0.0,
        log_path="rtt_measurements.csv",
    ):
        gr.basic_block.__init__(
            self,
            name="RTT Calculator",
            in_sig=[np.complex64, np.complex64],
            out_sig=[np.complex64],
        )
        self.samp_rate = samp_rate
        self.delay = delay_secs
        self.zc_duration = zc_length / samp_rate

        self.message_port_register_in(pmt.intern("tx_time_in"))
        self.set_msg_handler(pmt.intern("tx_time_in"), self.handle_tx_time)

        self.latest_tx_time_secs = 0.0
        self.last_rx_time = None
        self.last_tag_offset = 0

        self.zc_length = zc_length
        self.k_peak2noise = k_peak2noise
        self.fixed_threshold = fixed_threshold
        self.noise = 0.0
        self.phase_error = 0.0
        self.conlibration = -9.59849896077843E-06 # empirically determined correction to align with ground truth RTT at close range    

        # BPSK payload format: sync16 + id8 + (T2-T3)24 + measurement12 + crc8.
        # The responder currently sends [ZC31] + [100-sample gap] + [BPSK payload].
        self.sps = 60
        self.n_bits = packet_utils.RESPONSE_PACKET_BITS
        self.payload_offset = 100
        self.payload_len = (self.n_bits) * self.sps
        self.ts_bits = packet_utils.T2_MINUS_T3_BITS
        self.ts_mask = (1 << self.ts_bits) - 1

        # Per-measurement raw-IQ capture window emitted on output port 0.
        # Layout:
        #   [pre-noise] + [ZC preamble] + [gap] + [BPSK payload] + [tail]
        # If RESPONSE_PACKET_BITS == 56, this becomes:
        #   2000 + 839 + 100 + 3360 + 500 = 6799 complex samples.
        self.capture_pre_noise_len = 2000
        self.capture_tail_len = 500
        self.capture_window_len = int(
            self.capture_pre_noise_len
            + self.zc_length
            + self.payload_offset
            + self.payload_len
            + self.capture_tail_len
        )
        self.capture_queue = []
        self.max_capture_queue = 32
        self.capture_windows_dropped = 0

        # Rolling raw-sample buffer for payloads that cross GNU Radio scheduler buffers.
        # Absolute sample index is in the input-1 raw-complex stream domain.
        self.raw_buffer = np.zeros(0, dtype=np.complex64)
        self.raw_buffer_abs_start = 0
        self.raw_buffer_abs_end = 0
        min_history = self.capture_window_len
        self.raw_buffer_max_len = int(max(65536, 4 * min_history))
        self.pending_events = []
        self.max_pending_events = 32

        self.distance_setting_m = float(distance_setting_m)
        self.measurement_count = 0
        self.log_path = self._resolve_log_path(log_path)
        self.csv_fields = [
            "measurement_index",
            "log_time_utc",
            "latest_tx_time_secs",
            "rx_peak_secs",
            "distance_setting_m",
            "distance_fix_m",
            "tof_us",
            "tof_without_curvefit_us",
            "rx_time_tag_secs",
            "time_offset_s",
            "peak_frac_s",
            "peak_value",
            "noise_floor",
            "threshold",
            "corr_peak_metric_db",
            "phase_error",
            "responder_id",
            "t2_minus_t3",
            "measurement_number",
            "reply_delay_samples",
            "samp_rate",
            "zc_length",
            "delay_secs",
            "k_peak2noise",
            "fixed_threshold",
        ]
        self._ensure_csv_header()
        print(f"[RTT CSV] logging to: {self.log_path}")
        print(f"[RTT CSV] distance_setting_m: {self.distance_setting_m}")
        print(
            "[RX] rolling buffer enabled: "
            f"max_len={self.raw_buffer_max_len}, payload_len={self.payload_len}"
        )
        print(
            "[RX] raw capture output enabled: "
            f"pre_noise={self.capture_pre_noise_len}, "
            f"zc={self.zc_length}, gap={self.payload_offset}, "
            f"payload={self.payload_len}, tail={self.capture_tail_len}, "
            f"window_len={self.capture_window_len}"
        )

    def _resolve_log_path(self, log_path):
        path = os.path.expanduser(str(log_path))
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        return path

    def _ensure_csv_header(self):
        log_dir = os.path.dirname(self.log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        needs_header = (
            not os.path.exists(self.log_path)
            or os.path.getsize(self.log_path) == 0
        )

        if not needs_header:
            with open(self.log_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                existing_header = next(reader, [])

            if existing_header != self.csv_fields:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                backup_path = f"{self.log_path}.schema_mismatch_{timestamp}.bak"
                os.rename(self.log_path, backup_path)
                print(
                    "[RTT CSV] schema changed, old log moved to: "
                    f"{backup_path}"
                )
                needs_header = True

        if needs_header:
            with open(self.log_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.csv_fields)
                writer.writeheader()

    def _append_csv_row(self, row):
        with open(self.log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.csv_fields)
            writer.writerow(row)

    def set_distance_setting_m(self, distance_setting_m):
        self.distance_setting_m = float(distance_setting_m)
        print(f"[RTT CSV] distance_setting_m updated: {self.distance_setting_m}")

    def set_log_path(self, log_path):
        self.log_path = self._resolve_log_path(log_path)
        self._ensure_csv_header()
        print(f"[RTT CSV] logging to: {self.log_path}")

    def handle_tx_time(self, msg):
        sec = pmt.to_uint64(pmt.tuple_ref(msg, 0))
        frac = pmt.to_double(pmt.tuple_ref(msg, 1))
        self.latest_tx_time_secs = sec + frac

    def _append_raw_buffer(self, samples, abs_start):
        """Append raw complex samples to a rolling buffer indexed by absolute sample count."""
        samples = np.asarray(samples, dtype=np.complex64)
        abs_start = int(abs_start)
        abs_end = abs_start + len(samples)

        if len(samples) == 0:
            return

        if self.raw_buffer.size == 0:
            self.raw_buffer = samples.copy()
            self.raw_buffer_abs_start = abs_start
            self.raw_buffer_abs_end = abs_end
        elif abs_start == self.raw_buffer_abs_end:
            self.raw_buffer = np.concatenate((self.raw_buffer, samples))
            self.raw_buffer_abs_end = abs_end
        elif abs_start > self.raw_buffer_abs_end:
            # Discontinuity. Keep the newest contiguous segment.
            print(
                "[RX] raw rolling buffer discontinuity, reset: "
                f"old_end={self.raw_buffer_abs_end}, new_start={abs_start}"
            )
            self.raw_buffer = samples.copy()
            self.raw_buffer_abs_start = abs_start
            self.raw_buffer_abs_end = abs_end
        else:
            # Overlap or duplicate samples. Append only the part not already stored.
            overlap = self.raw_buffer_abs_end - abs_start
            if overlap < len(samples):
                self.raw_buffer = np.concatenate((self.raw_buffer, samples[overlap:]))
                self.raw_buffer_abs_end = abs_end
            # else: the incoming window is already fully covered.

        self._trim_raw_buffer()

    def _trim_raw_buffer(self):
        if len(self.raw_buffer) <= self.raw_buffer_max_len:
            return

        keep_len = self.raw_buffer_max_len
        drop_len = len(self.raw_buffer) - keep_len
        self.raw_buffer = self.raw_buffer[drop_len:].copy()
        self.raw_buffer_abs_start += drop_len

    def _get_raw_window(self, abs_start, length):
        """
        Return a copy of a raw-complex window when it is available.

        Status values:
            ready   : window returned
            w:waiting : future samples are still needed
            e:expired : requested samples already fell out of the rolling buffer
        """
        abs_start = int(abs_start)
        abs_end = int(abs_start + length)

        if abs_start < self.raw_buffer_abs_start:
            return None, "e"
        if abs_end > self.raw_buffer_abs_end:
            return None, "w"

        local_start = abs_start - self.raw_buffer_abs_start
        local_end = local_start + length
        return self.raw_buffer[local_start:local_end].copy(), "ready"

    def _queue_capture_window(self, samples, event, responder_id, measurement_number):
        """Queue one fixed-length raw-IQ capture window for output port 0."""
        samples = np.asarray(samples, dtype=np.complex64)

        if len(samples) != self.capture_window_len:
            print(
                "[RX CAPTURE] invalid capture length, dropped: "
                f"got={len(samples)}, expected={self.capture_window_len}"
            )
            return

        if len(self.capture_queue) >= self.max_capture_queue:
            self.capture_queue.pop(0)
            self.capture_windows_dropped += 1
            print(
                "[RX CAPTURE] output queue full, dropped oldest window. "
                f"dropped_total={self.capture_windows_dropped}"
            )

        self.capture_queue.append({
            "samples": samples.copy(),
            "pos": 0,
            "capture_start_abs": int(event["capture_start_abs"]),
            "capture_end_abs": int(event["capture_end_abs"]),
            "peak_abs": int(event["peak_abs"]),
            "payload_start_abs": int(event["payload_start_abs"]),
            "measurement_index": int(self.measurement_count + 1),
            "measurement_number": int(measurement_number),
            "responder_id": int(responder_id),
            "phase_error": float(event["phase_error"]),
        })

    def _produce_capture_output(self, out, produced):
        """
        Emit queued capture windows on output port 0.

        The output stream is a concatenation of fixed-length windows. If connected
        to a normal File Sink, tags are not preserved, so split the file offline by
        self.capture_window_len complex64 samples.
        """
        n_output = len(out)

        while self.capture_queue and produced < n_output:
            item = self.capture_queue[0]
            samples = item["samples"]
            pos = int(item["pos"])
            remaining_window = len(samples) - pos
            room = n_output - produced
            to_copy = min(remaining_window, room)

            out_start = produced
            out_end = produced + to_copy
            out[out_start:out_end] = samples[pos:pos + to_copy]

            abs_out_start = int(self.nitems_written(0) + produced)

            if pos == 0:
                src = pmt.intern("rtt_capture")
                self.add_item_tag(0, abs_out_start, pmt.intern("capture_sob"), pmt.PMT_T, src)
                self.add_item_tag(0, abs_out_start, pmt.intern("capture_len"), pmt.from_uint64(self.capture_window_len), src)
                self.add_item_tag(0, abs_out_start, pmt.intern("capture_start_abs"), pmt.from_uint64(item["capture_start_abs"]), src)
                self.add_item_tag(0, abs_out_start, pmt.intern("capture_peak_abs"), pmt.from_uint64(item["peak_abs"]), src)
                self.add_item_tag(0, abs_out_start, pmt.intern("payload_start_abs"), pmt.from_uint64(item["payload_start_abs"]), src)
                self.add_item_tag(0, abs_out_start, pmt.intern("measurement_index"), pmt.from_uint64(item["measurement_index"]), src)
                if item["responder_id"] >= 0:
                    self.add_item_tag(0, abs_out_start, pmt.intern("responder_id"), pmt.from_uint64(item["responder_id"]), src)
                if item["measurement_number"] >= 0:
                    self.add_item_tag(0, abs_out_start, pmt.intern("measurement_number"), pmt.from_uint64(item["measurement_number"]), src)
                self.add_item_tag(0, abs_out_start, pmt.intern("phase_error"), pmt.from_double(item["phase_error"]), src)

            produced += to_copy
            item["pos"] = pos + to_copy

            if item["pos"] >= len(samples):
                abs_out_last = int(self.nitems_written(0) + produced - 1)
                self.add_item_tag(
                    0,
                    abs_out_last,
                    pmt.intern("capture_eob"),
                    pmt.PMT_T,
                    pmt.intern("rtt_capture"),
                )
                self.capture_queue.pop(0)

        return produced

    def find_peak_indices(self, in_sig):
        magnitude = in_sig
        noise_floor = float(np.mean(magnitude))
        threshold = max(noise_floor * self.k_peak2noise, self.fixed_threshold)
        candidate_indices = np.where(magnitude > threshold)[0]

        if candidate_indices.size == 0:
            return None, None, {
                "noise_floor": noise_floor,
                "threshold": float(threshold),
                "peak_value": 0.0,
                "corr_peak_metric_db": float("-inf"),
            }

        peak_indices = int(candidate_indices[np.argmax(magnitude[candidate_indices])])
        peak_value = float(magnitude[peak_indices])
        noise_safe = max(noise_floor, np.finfo(float).eps)
        corr_snr_linear = peak_value / noise_safe
        corr_peak_metric_db = 20.0 * np.log10(corr_snr_linear)

        if 1 <= peak_indices < len(magnitude) - 1:
            y_m1 = magnitude[peak_indices - 1]
            y_0 = magnitude[peak_indices]
            y_p1 = magnitude[peak_indices + 1]

            den = y_m1 - 2 * y_0 + y_p1
            if abs(den) > 1e-12:
                delta = 0.5 * (y_m1 - y_p1) / den / self.samp_rate
                delta = np.clip(delta, -0.5 / self.samp_rate, 0.5 / self.samp_rate)
            else:
                delta = 0.0
        else:
            delta = 0.0

        return peak_indices, float(delta), {
            "noise_floor": noise_floor,
            "threshold": float(threshold),
            "peak_value": peak_value,
            "corr_peak_metric_db": float(corr_peak_metric_db),
        }

    def bpsk_demod(self, payload_samples, n_bits=None, sps=None, phase_error=None):
        if n_bits is None:
            n_bits = self.n_bits
        if sps is None:
            sps = self.sps
        if phase_error is None:
            phase_error = self.phase_error

        symbols = []
        payload_samples = payload_samples * np.exp(-1j * phase_error)
        for k in range(n_bits):
            start = k * sps
            stop = (k + 1) * sps

            a = start + sps // 4
            b = stop - sps // 4

            symbols.append(np.mean(payload_samples[a:b]))

        symbols = np.asarray(symbols, dtype=np.complex64)

        bits = []
        metrics = []

        for k in range(0, len(symbols)):
            z = symbols[k]
            bit = 1 if np.real(z) < 0 else 0
            bits.append(bit)
            metrics.append(float(np.real(z)))

        return bits, metrics

    def _queue_event(self, event):
        if len(self.pending_events) >= self.max_pending_events:
            dropped = self.pending_events.pop(0)
            # print(
            #     "[RX] pending payload queue full, dropped oldest event: "
            #     f"peak_abs={dropped.get('peak_abs')}"
            # )
        self.pending_events.append(event)
        # print(
        #     "[RX] payload pending: "
        #     f"need=[{event['payload_start_abs']}, {event['payload_end_abs']}), "
        #     f"buffer=[{self.raw_buffer_abs_start}, {self.raw_buffer_abs_end})"
        # )

    def _try_process_event(self, event):
        payload, payload_status = self._get_raw_window(
            event["payload_start_abs"], self.payload_len
        )
        capture, capture_status = self._get_raw_window(
            event["capture_start_abs"], self.capture_window_len
        )

        # Wait until both payload and tail margin are available. This delays the
        # measurement by capture_tail_len samples, but keeps the capture window complete.
        if payload_status == "w" or capture_status == "w":
            return False

        if payload_status == "e":
            # print(
            #     "[RX] pending payload expired: "
            #     f"need_start={event['payload_start_abs']}, "
            #     f"buffer_start={self.raw_buffer_abs_start}"
            # )
            return True

        if capture_status == "e":
            # print(
            #     "[RX CAPTURE] capture window expired; measurement will be kept without IQ output: "
            #     f"need_start={event['capture_start_abs']}, "
            #     f"buffer_start={self.raw_buffer_abs_start}"
            # )
            capture = None

        bits, metrics = self.bpsk_demod(
            payload,
            n_bits=self.n_bits,
            sps=self.sps,
            phase_error=event["phase_error"],
        )

        try:
            (
                responder_id,
                t2_minus_t3,
                measurement_number,
            ) = packet_utils.decode_response_packet(bits)
            reply_delay_samples = int((-int(t2_minus_t3)) & self.ts_mask)
            reply_delay_secs = reply_delay_samples / float(self.samp_rate)
            # print(
            #     "[RX] payload decoded: "
            #     f"Responder ID={responder_id}, "
            #     f"T2-T3={t2_minus_t3}, measurement={measurement_number}, "
            #     f"reply_delay={reply_delay_samples} samples"
            # )
        except Exception as exc:
            # Keep measurement flow alive while packet format is still under development.
            responder_id = -1
            t2_minus_t3 = 0
            measurement_number = -1
            reply_delay_samples = int(round(self.delay * self.samp_rate))
            reply_delay_secs = float(self.delay)
            print(f"[RX] payload decode failed, fallback to configured delay: {exc}")

        if capture is not None:
            self._queue_capture_window(
                samples=capture,
                event=event,
                responder_id=responder_id,
                measurement_number=measurement_number,
            )

        self._finalize_measurement(
            event=event,
            responder_id=responder_id,
            t2_minus_t3=t2_minus_t3,
            measurement_number=measurement_number,
            reply_delay_samples=reply_delay_samples,
            reply_delay_secs=reply_delay_secs,
        )
        return True

    def _process_pending_events(self):
        if not self.pending_events:
            return

        remaining = []
        for event in self.pending_events:
            done = self._try_process_event(event)
            if not done:
                remaining.append(event)
        self.pending_events = remaining

    def _finalize_measurement(
        self,
        event,
        responder_id,
        t2_minus_t3,
        measurement_number,
        reply_delay_samples,
        reply_delay_secs,
    ):
        # Matched-filter peak is treated as the end of the received ZC preamble.
        rx_peak_secs = event["rx_peak_secs"]
        tx_time_secs = event["tx_time_secs"]
        k_frac = event["peak_frac_s"]
        peak_metrics = event["peak_metrics"]

        round_trip_flight_time = rx_peak_secs - tx_time_secs - reply_delay_secs 
        tof = (round_trip_flight_time + k_frac) / 2 + self.conlibration
        distance_fix = tof * 299792458

        self.measurement_count += 1
        self.noise = peak_metrics["noise_floor"]
        self._append_csv_row({
            "measurement_index": self.measurement_count,
            "log_time_utc": datetime.now(timezone.utc).isoformat(),
            "latest_tx_time_secs": f"{tx_time_secs:.12f}",
            "rx_peak_secs": f"{rx_peak_secs:.12f}",
            "distance_setting_m": f"{self.distance_setting_m:.6f}",
            "distance_fix_m": f"{distance_fix:.9f}",
            "tof_us": f"{tof * 1e6:.9f}",
            "tof_without_curvefit_us": f"{round_trip_flight_time/2*1e6:.12f}",
            "rx_time_tag_secs": f"{event['rx_time_tag_secs']:.12f}",
            "time_offset_s": f"{event['time_offset_s']:.12f}",
            "peak_frac_s": f"{k_frac:.12e}",
            "peak_value": f"{peak_metrics['peak_value']:.9f}",
            "noise_floor": f"{peak_metrics['noise_floor']:.9f}",
            "threshold": f"{peak_metrics['threshold']:.9f}",
            "corr_peak_metric_db": f"{peak_metrics['corr_peak_metric_db']:.9f}",
            "phase_error": f"{event['phase_error']:.6f}",
            "responder_id": int(responder_id),
            "t2_minus_t3": int(t2_minus_t3),
            "measurement_number": int(measurement_number),
            "reply_delay_samples": int(reply_delay_samples),
            "samp_rate": self.samp_rate,
            "zc_length": self.zc_length,
            "delay_secs": self.delay,
            "k_peak2noise": self.k_peak2noise,
            "fixed_threshold": self.fixed_threshold,
        })

        # print(f"[RTT] measurement #{self.measurement_count}")
        # print(f"[RTT] ToF: {tof * 1e6:.6f} us")
        # print(f"[RTT] distance_fix: {distance_fix:.4f} m")
        # print(
        #     "[RTT] corr noise_floor: "
        #     f"{peak_metrics['noise_floor']:.4f}, "
        #     f"SNR: {peak_metrics['corr_peak_metric_db']:.2f} dB"
        # )

    def general_work(self, input_items, output_items):
        out = output_items[0]
        n = min(len(input_items[0]), len(input_items[1]))
        produced = 0
        if n <= 0:
            produced = self._produce_capture_output(out, produced)
            self.produce(0, produced)
            return gr.WORK_CALLED_PRODUCE

        corr = input_items[0][:n]
        rx_complex = input_items[1][:n]

        corr_abs_start = int(self.nitems_read(0))
        raw_abs_start = int(self.nitems_read(1))

        # Store raw samples before detection, so a payload fully inside the current
        # scheduler buffer can be decoded immediately.
        self._append_raw_buffer(rx_complex, raw_abs_start)

        tags = self.get_tags_in_window(1, 0, n)
        for tag in tags:
            if pmt.symbol_to_string(tag.key) == "rx_time":
                self.last_rx_time = tag.value
                self.last_tag_offset = int(tag.offset)

        # First, retry events whose payloads were incomplete in previous calls.
        self._process_pending_events()

        magnitude = np.abs(corr)
        peak_indices, k_frac, peak_metrics = self.find_peak_indices(magnitude)
        if peak_indices is None:
            produced = self._produce_capture_output(out, produced)
            self.consume(0, n)
            self.consume(1, n)
            self.produce(0, produced)
            return gr.WORK_CALLED_PRODUCE

        phase_error = float(np.angle(corr[peak_indices]))
        self.phase_error = phase_error

        if self.last_rx_time is not None and self.latest_tx_time_secs > 0:
            tx_time_secs = float(self.latest_tx_time_secs)
            current_peak_offset = corr_abs_start + int(peak_indices)
            diff_samples = current_peak_offset - self.last_tag_offset
            time_offset = diff_samples / float(self.samp_rate)

            rx_sec = int(pmt.to_uint64(pmt.tuple_ref(self.last_rx_time, 0)))
            rx_frac = float(pmt.to_double(pmt.tuple_ref(self.last_rx_time, 1)))
            rx_time_tag_secs = rx_sec + rx_frac

            # The matched-filter peak is the end of the ZC preamble.
            rx_peak_secs = rx_time_tag_secs + time_offset - self.zc_duration

            payload_start_abs = int(current_peak_offset + self.payload_offset)
            payload_end_abs = int(payload_start_abs + self.payload_len)
            zc_start_abs = int(current_peak_offset - self.zc_length + 1)
            capture_start_abs = int(zc_start_abs - self.capture_pre_noise_len)
            capture_end_abs = int(capture_start_abs + self.capture_window_len)

            event = {
                "tx_time_secs": tx_time_secs,
                "peak_abs": int(current_peak_offset),
                "zc_start_abs": zc_start_abs,
                "payload_start_abs": payload_start_abs,
                "payload_end_abs": payload_end_abs,
                "capture_start_abs": capture_start_abs,
                "capture_end_abs": capture_end_abs,
                "phase_error": phase_error,
                "rx_peak_secs": rx_peak_secs,
                "rx_time_tag_secs": rx_time_tag_secs,
                "time_offset_s": time_offset,
                "peak_frac_s": float(k_frac),
                "peak_metrics": peak_metrics,
            }

            # print("[RX] valid peak and tx_time found")
            done = self._try_process_event(event)
            if not done:
                self._queue_event(event)

            # Bind this tx_time to exactly one response event. Future payload completion
            # uses the stored tx_time in event, so the message state can be cleared now.
            self.latest_tx_time_secs = 0.0
            print(f"[RX] Measurement {self.measurement_count}: Valid peak and tx_time found")
        else:
            print("[RX] peak found but rx_time or tx_time is missing")
            print(f"    - last_rx_time: {self.last_rx_time}")
            print(f"    - latest_tx_time_secs: {self.latest_tx_time_secs:.6f} s")
            print(f"    - peak index: {peak_indices}, last_tag_offset: {self.last_tag_offset}")

        produced = self._produce_capture_output(out, produced)

        self.consume(0, n)
        self.consume(1, n)
        self.produce(0, produced)
        return gr.WORK_CALLED_PRODUCE
