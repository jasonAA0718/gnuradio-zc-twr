# CODEX TASK: Convert ZC Burst TW-RTT Project to OFDM / PRS-like Ranging Reference Signal with GNU Radio OOT C++ Blocks

Date: 2026-06-30
Target repo: current GNU Radio ZC TW-RTT project
Primary target parameters:

```text
Center frequency: 1399 MHz
Sample rate: 10 MHz
Initial mode: one-way OFDM / PRS-like ranging reference signal
Implementation target: GNU Radio OOT module in C++
Do not delete the existing ZC + BPSK system. Keep it buildable while adding the OFDM / PRS path.
```

---

## 0. Current project context

The current project is a GNU Radio / USRP ZC + BPSK TW-RTT ranging prototype.

Current high-level flow:

```text
Initiator sends ZC25 request
Responder detects ZC25 request peak
Responder estimates T2 from USRP rx_time tag and sample offset
Responder sets T3 = T2 + 5 ms
Responder transmits timed response burst with tx_time
Responder response = [ZC31] + [gap] + [BPSK payload] + [tail guard]
Initiator detects ZC31 response peak
Initiator decodes responder_id, T2-T3, measurement_number, CRC
Initiator computes reply_delay_samples and RTT / ToF
```

Important current implementation details:

```text
Sample rate: 10 MHz
Center frequency option: 917 MHz or 1399 MHz
ZC length: 839 samples
Request ZC root: 25
Response ZC root: 31
Responder reply delay: 5 ms
reply_delay_samples: 50,000 samples at 10 MHz
Payload: 68 bits
Payload Sync: 0xA5C3
Responder ID: 8 bit
T2-T3: 24 bit
Measurement Number: 12 bit
CRC8: 8 bit
BPSK samples per symbol: 60
BPSK payload length: 4080 samples
Response burst length: 5119 complex samples
```

Current known issues to preserve or fix during migration:

```text
1. Raw-IQ capture output exists but is still connected to Null Sink in tx.py.
2. matched-filter peak alignment has possible 1-sample ambiguity.
3. ZC peak phase correction only gives one burst-level phase correction.
4. CFO can rotate payload phase over time.
5. decode fallback to fixed delay can pollute ranging statistics.
6. Current detector may process only one peak per general_work buffer.
```

---

## 1. Main engineering goal

Add a new OFDM / PRS-like ranging reference signal path using C++ OOT blocks.

Do not fully rewrite the TWR protocol in the first pass. The first pass should make this work:

```text
TX: generate deterministic OFDM / PRS-like frame at 10 MHz, 1399 MHz
RX: capture raw-IQ and optionally detect PRS frames
Offline or PDU estimator: estimate coarse frame start, CFO, channel H[k], phase slope, fine ToA
```

The final expected architecture is:

```text
USRP stream
→ coarse sync / frame extractor
→ frame PDU
→ OFDM PRS estimator PDU
→ measurement PDU
→ later TW-RTT or DS-TWR solver
```

For TX:

```text
QT trigger or message
→ PRS frame builder / timed burst source
→ complex stream with tx_time / tx_sob / tx_eob tags
→ UHD USRP Sink
```

---

## 2. Required waveform design

Use this initial OFDM / PRS-like frame at 10 MHz:

```text
zero guard                  1000 samples
short repeated preamble      128 samples × 16 repeats = 2048 samples
coarse sync                  839 samples, may reuse ZC length for now
OFDM PRS block               16 × (1024 + 128) = 18432 samples
tail guard                   1000 samples
-------------------------------------------------------------
total                        23319 samples
duration at 10 MHz           2.3319 ms
```

Primary OFDM parameters:

```text
samp_rate:       10e6
center_freq:     1399e6
fft_len:         1024
cp_len:          128
active_bins:     600
active bins:     -300 ... -1, +1 ... +300
DC bin:          disabled
PRS symbols:     16
pilot type:      deterministic QPSK
pilot seed:      fixed, do not randomize per execution unless frame_id controls it
```

Subcarrier spacing:

```text
10e6 / 1024 = 9765.625 Hz
```

Active occupied bandwidth:

```text
600 × 9765.625 Hz ≈ 5.859375 MHz
```

Frame naming:

```text
OFDM PRS frame
PRS block
coarse sync
short preamble
```

Do not call it an OFDM pulse. It is a burst-mode OFDM ranging frame.

---

## 3. Required OOT module

Create a new GNU Radio OOT module instead of placing all new logic in Embedded Python Blocks.

Preferred module name:

```text
gr-ofdm_prs_ranging
```

If the current repo already uses a different OOT module name, use that existing naming convention and add the blocks inside it.

Suggested bootstrap commands:

```bash
gr_modtool newmod ofdm_prs_ranging
gr_modtool add -t general -l cpp prs_timed_burst_source
gr_modtool add -t general -l cpp prs_frame_detector
gr_modtool add -t noblock -l cpp prs_pdu_estimator
```

If `noblock` is not available in the installed GNU Radio version, create `prs_pdu_estimator` as a `gr::block` with no stream ports and only message ports.

The OOT must include:

```text
C++ implementation files
C++ headers
CMake updates
GRC block YAML files
Python binding if the local GNU Radio version requires it
QA tests
Example GRC files
README notes
```

---

## 4. Block 1: prs_timed_burst_source

### Purpose

Generate deterministic OFDM / PRS-like bursts and output them as a complex stream. Attach GNU Radio stream tags for UHD timed TX.

### Block type

Use `gr::block` with:

```text
Input 0: complex stream, optional in concept but implemented as required input for now
Output 0: complex stream
Message input: trigger
Message output: tx_time_out
```

Input 0 is only used to read `rx_time` tags and track current USRP hardware time, similar to the existing manual ping generator behavior.

### Parameters

```text
samp_rate: double, default 10e6
fft_len: int, default 1024
cp_len: int, default 128
active_bins: int, default 600
prs_symbols: int, default 16
preamble_len: int, default 128
preamble_repeats: int, default 16
coarse_sync_len: int, default 839
zero_guard_len: int, default 1000
tail_guard_len: int, default 1000
tx_lead_time: double, default 0.5
burst_period: double, default 0.1
tx_amp: float, default 0.2
seed: uint32_t, default 13990001
pings_per_trigger: int, default 1
attach_tx_time: bool, default true
```

### Output tags

At first output sample of each burst:

```text
tx_time
tx_sob
frame_id
burst_len
prs_start
prs_len
fft_len
cp_len
active_bins
samp_rate
```

At last output sample of each burst:

```text
tx_eob
```

### Message output

On each scheduled transmit, send a PMT dict on `tx_time_out`:

```text
frame_id
tx_time_secs
tx_time_frac
burst_len
prs_start
prs_len
fft_len
cp_len
active_bins
```

### Frame generation details

Generate once at construction or when parameters change:

```text
1. zero guard
2. repeated short preamble
3. coarse sync sequence
4. OFDM PRS symbols
5. tail guard
```

Normalize waveform:

```text
RMS amplitude after frame generation should be controlled by tx_amp.
Do not allow max absolute sample to exceed 0.8.
Avoid clipping because OFDM has high PAPR.
```

### OFDM generation

Use frequency-domain vector `X` of length `fft_len`:

```text
X[DC] = 0
X[guard bins] = 0
X[active_bins] = deterministic QPSK pilots
```

Then:

```text
x = IFFT(ifftshift(X))
x_cp = last cp_len samples of x + x
```

Use the same active bin indexing convention in TX and RX.

---

## 5. Block 2: prs_frame_detector

### Purpose

Detect PRS frames from a raw complex stream while preserving sample-accurate timing. Output each extracted frame as a PDU with metadata.

### Block type

Use `gr::block` with:

```text
Input 0: complex stream
No stream output
Message output: frame_out
```

### Required behavior

```text
1. Read rx_time tags.
2. Maintain absolute sample counter.
3. Maintain rolling buffer large enough for at least 4 frames.
4. Correlate with coarse sync or short preamble.
5. Detect frame start using threshold and peak-to-noise metric.
6. Extract complete frame samples after enough samples arrive.
7. Output a PDU containing complex64 frame samples and metadata.
8. Support multiple frame candidates in one scheduler buffer.
```

### Parameters

```text
samp_rate: double, default 10e6
fft_len: int, default 1024
cp_len: int, default 128
active_bins: int, default 600
prs_symbols: int, default 16
preamble_len: int, default 128
preamble_repeats: int, default 16
coarse_sync_len: int, default 839
zero_guard_len: int, default 1000
tail_guard_len: int, default 1000
fixed_threshold: float, default 0.0
k_peak2noise: float, default 12.0
min_frame_gap_samples: int, default 10000
max_pending_frames: int, default 32
```

### PDU metadata

The `frame_out` PDU metadata must include:

```text
frame_id_detected, if available
rx_time_secs
rx_time_frac
rx_time_tag_offset
abs_start_sample
frame_start_abs
coarse_peak_abs
coarse_peak_value
noise_floor
peak_metric_db
samp_rate
fft_len
cp_len
active_bins
prs_start_abs
prs_start_rel
prs_len
burst_len
```

### Data

PDU data must be a c32 vector containing the extracted frame samples.

### Important

Do not convert the whole USRP stream to PDU at the input. Detect frame boundaries in stream first, then output a frame PDU.

---

## 6. Block 3: prs_pdu_estimator

### Purpose

Estimate CFO, OFDM channel, phase slope, and fine ToA from a frame PDU.

### Block type

Message-only block:

```text
Message input: frame_in
Message output: meas_out
Optional message output: debug_out
```

### Required processing

```text
1. Read metadata and frame samples.
2. Estimate CFO using repeated short preamble.
3. Apply CFO correction to frame samples.
4. Slice OFDM PRS symbols using prs_start_rel, fft_len, and cp_len.
5. Remove CP.
6. FFT each OFDM symbol.
7. Extract active subcarriers.
8. Regenerate deterministic QPSK pilot X[k].
9. Compute H[k] = Y[k] / X[k].
10. Average H[k] across PRS symbols.
11. Unwrap phase across active subcarriers.
12. Estimate delay from phase slope.
13. Compute quality metrics.
14. Output measurement PDU.
```

### Phase slope equation

Use active subcarrier frequencies `f_k` relative to baseband:

```text
angle(H[k]) ≈ phi0 - 2*pi*f_k*tau
```

Estimate `tau` using weighted least squares:

```text
tau_hat = -1/(2*pi) * sum(w_k * (f_k - f_bar) * (phi_k - phi_bar)) / sum(w_k * (f_k - f_bar)^2)
```

Initial weights:

```text
w_k = |H[k]|^2
```

### Measurement metadata

The `meas_out` message should include:

```text
frame_id
coarse_peak_abs
coarse_toa_s
fine_delay_s
fine_delay_samples
cfo_hz
snr_est_db
phase_slope
phase_residual_rms
channel_power_mean
multipath_metric
peak_metric_db
valid
error_reason
```

### Initial validity criteria

Set `valid = false` if:

```text
1. PDU length is shorter than expected frame length.
2. PRS block does not fit inside frame.
3. CFO estimate is NaN or unreasonable.
4. phase unwrap fails.
5. phase_residual_rms is above a configurable threshold.
```

---

## 7. GRC flowgraphs to create

Create new GRC files. Do not destroy existing `tx.grc` and `rx.grc`.

### 7.1 prs_tx_10M_1399.grc

Blocks:

```text
UHD: USRP Source
  sample rate = 10e6
  center frequency = 1399e6
  used only to provide rx_time tags to prs_timed_burst_source

QT GUI Push Button
  message output → prs_timed_burst_source trigger

prs_timed_burst_source
  input 0 ← UHD Source raw stream
  output 0 → Multiply Const CC

Multiply Const CC
  constant = 1.0 initially, amplitude controlled inside block or set to 0.2 here

UHD: USRP Sink
  sample rate = 10e6
  center frequency = 1399e6
  gain = variable tx_gain

QT GUI Time Sink
QT GUI Frequency Sink
File Sink, optional TX reference output
```

### 7.2 prs_rx_capture_10M_1399.grc

Blocks:

```text
UHD: USRP Source
  sample rate = 10e6
  center frequency = 1399e6
  gain = variable rx_gain

File Sink, complex64
  output path = captures/rx_prs_10M_1399.c64

QT GUI Time Sink
QT GUI Frequency Sink
```

### 7.3 prs_rx_estimator_10M_1399.grc

Blocks:

```text
UHD: USRP Source
  ↓
prs_frame_detector
  frame_out message ↓
prs_pdu_estimator
  meas_out message ↓
Message Debug or custom CSV logger
```

For the first pass, raw capture flowgraph is higher priority than live estimator.

---

## 8. Testing requirements

### 8.1 Unit tests

Add QA tests that do not require USRP hardware.

Test 1: waveform length

```text
Generate default frame.
Expected length: 23319 complex samples.
```

Test 2: active subcarrier mapping

```text
Generate one OFDM PRS symbol.
Verify 600 active bins are non-zero.
Verify DC is zero.
Verify guard bins are zero.
```

Test 3: detector on synthetic signal

```text
Create random noise prefix.
Insert one PRS frame.
Run detector.
Expected: frame_start_abs within 1 sample of inserted position.
```

Test 4: estimator with no channel impairment

```text
Input clean frame.
Expected: CFO near 0.
Expected: fine_delay_samples near 0.
```

Test 5: estimator with fractional delay

```text
Apply synthetic fractional delay, for example 2.35 samples.
Expected: fine_delay_samples close to 2.35.
Tolerance for first implementation: <= 0.2 sample.
```

Test 6: estimator with CFO

```text
Apply CFO, for example 500 Hz.
Expected: CFO estimate close enough for stable phase slope.
Expected: valid = true at SNR >= 20 dB.
```

### 8.2 Manual loopback test

Use cable loopback with attenuator:

```text
USRP TX → 30 to 60 dB attenuation → USRP RX
```

Expected first milestone:

```text
Frame detection rate > 99 percent
No ADC clipping
CFO estimate stable
fine_delay_samples standard deviation < 0.1 sample in cable loopback at good SNR
```

---

## 9. Build commands

Use these commands after adding OOT module files:

```bash
mkdir -p build
cd build
cmake ..
make -j$(nproc)
ctest --output-on-failure
sudo make install
sudo ldconfig
```

After installing, refresh GNU Radio block cache if needed:

```bash
gnuradio-companion
```

If blocks do not appear, check:

```bash
echo $GRC_BLOCKS_PATH
echo $PYTHONPATH
echo $LD_LIBRARY_PATH
gnuradio-config-info --version
```

---

## 10. Migration phases

### Phase 1: Add OOT blocks without touching old RTT flowgraphs

Deliverables:

```text
gr-ofdm_prs_ranging OOT module builds
prs_timed_burst_source block works
prs_tx_10M_1399.grc can transmit deterministic frame
prs_rx_capture_10M_1399.grc can save raw-IQ
QA tests pass
```

### Phase 2: Offline analysis and estimator validation

Deliverables:

```text
prs_frame_detector works on File Source or UHD Source
prs_pdu_estimator outputs CFO and fine_delay_samples
CSV log can be produced from meas_out messages
Cable loopback repeatability measured
```

### Phase 3: Replace ZC response reference with PRS response reference

Modify current responder response burst from:

```text
[ZC31] + [100-sample gap] + [68-bit BPSK payload] + [100-sample tail guard]
```

To:

```text
[short repeated preamble] + [coarse sync] + [OFDM PRS block] + [payload] + [tail guard]
```

Keep current payload fields initially:

```text
Payload Sync 0xA5C3
Responder ID
T2-T3 24 bit
Measurement Number 12 bit
CRC8
```

### Phase 4: Replace ZC request reference with PRS request reference

Modify initiator request from:

```text
[ZC25]
```

To:

```text
[short repeated preamble] + [coarse sync] + [OFDM PRS block] + optional payload
```

### Phase 5: Upgrade TW-RTT to DS-TWR

Do this only after OFDM / PRS estimator is stable.

---

## 11. Do not do these in the first pass

```text
Do not delete the existing ZC blocks.
Do not edit only generated Python files and ignore the .grc source.
Do not implement DS-TWR immediately.
Do not optimize for 20 km yet.
Do not add FEC yet.
Do not use GNU Radio standard OFDM packet chain as the first implementation.
Do not hide timing metadata. Preserve sample offsets and rx_time / tx_time related tags.
```

---

## 12. Expected Codex output

When complete, provide:

```text
1. Summary of changed files.
2. Build commands used.
3. Test commands used.
4. Any tests that failed and why.
5. New GRC files created.
6. How to run TX flowgraph.
7. How to run RX capture flowgraph.
8. How to run RX estimator flowgraph.
9. Notes about GNU Radio version compatibility.
```

---

## 13. Important note about editing GRC files

GNU Radio Companion flowgraphs are saved as text files with `.grc` extension. Codex may edit `.grc` files as XML/YAML text depending on the GNU Radio version. However, Codex cannot operate the visual GUI directly. After Codex modifies `.grc`, open the file in GNU Radio Companion to inspect block placement, missing parameters, and generated Python.

Prefer this workflow:

```text
1. Codex edits OOT C++ files and GRC text files.
2. Build and install OOT module.
3. Open .grc in GNU Radio Companion.
4. Resolve any visual block errors.
5. Generate Python from GRC.
6. Run the flowgraph.
```

Do not treat generated Python as the only source of truth if the `.grc` flowgraph still exists.

---

## 14. Minimal first Codex prompt

Use this prompt from the repo root:

```text
Read CODEX_OFDM_PRS_OOT_MIGRATION.md. Implement Phase 1 only. Add a GNU Radio OOT C++ module for OFDM / PRS-like ranging reference signal generation at 10 MHz and 1399 MHz. Do not delete or break the existing ZC + BPSK TW-RTT flowgraphs. Create prs_timed_burst_source, GRC YAML block definition, QA tests, and a new prs_tx_10M_1399.grc example. After each change, build and run tests. Report exactly what changed and what still needs manual verification in GNU Radio Companion.
```
