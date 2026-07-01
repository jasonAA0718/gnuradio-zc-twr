# GNU Radio ZC + BPSK TW-RTT Project

This repository manages the GNU Radio TX/RX flowgraphs and Python blocks for a ZC + BPSK two-way RTT ranging system.

## Structure

- `tx/`: Initiator GNU Radio flowgraph and Python blocks
- `rx/`: Responder GNU Radio flowgraph and Python blocks
- `common/`: Shared packet utilities
- `logs/`: Measurement logs, ignored by Git
- `captures/`: Raw IQ capture files, ignored by Git
- `gr-ofdm_prs_ranging/`: Additive GNU Radio OOT module for OFDM / PRS-like ranging frames

## Main Parameters

- Sample rate: 10 MHz
- ZC length: 839
- Request ZC root: 25
- Response ZC root: 31
- Reply delay: 5 ms

## OFDM / PRS Phase 1 Add-On

The `gr-ofdm_prs_ranging` OOT module adds `prs_timed_burst_source`, a C++ block that generates a deterministic burst-mode OFDM PRS-like frame at 10 MHz for 1399 MHz experiments.

Default frame geometry:

- Zero guard: 1000 samples
- Short repeated preamble: 128 samples x 16 repeats
- Coarse sync: 839 samples
- OFDM PRS block: 16 symbols x (1024 FFT + 128 CP)
- Tail guard: 1000 samples
- Total: 23319 complex samples

Example GRC files:

- `gr-ofdm_prs_ranging/examples/prs_tx_10M_1399.grc`
- `gr-ofdm_prs_ranging/examples/prs_rx_capture_10M_1399.grc`
- `gr-ofdm_prs_ranging/examples/prs_rx_estimator_10M_1399.grc`

The legacy `tx/tx.grc` and `rx/rx.grc` ZC + BPSK TW-RTT flowgraphs are unchanged.

## OFDM / PRS Phase 2 Receiver

The one-way receiver path is:

```text
UHD Source
-> PRS Frame Detector
-> PRS FFT Receiver
-> PRS Channel Estimator
-> PRS Phase Slope Estimator
-> PRS CSV Logger
```

It performs coarse frame detection, frame PDU extraction, CP removal, FFT, active subcarrier extraction, known-pilot channel estimation, phase-slope fine delay estimation, and CSV measurement logging. It does not implement RTT, DS-TWR, payload decoding, or a protocol state machine.

The CSV logger writes:

```text
frame_id,coarse_delay,fine_delay,cfo,snr,phase_residual,peak_metric,quality
```
