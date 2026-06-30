# GNU Radio ZC + BPSK TW-RTT Project

This repository manages the GNU Radio TX/RX flowgraphs and Python blocks for a ZC + BPSK two-way RTT ranging system.

## Structure

- `tx/`: Initiator GNU Radio flowgraph and Python blocks
- `rx/`: Responder GNU Radio flowgraph and Python blocks
- `common/`: Shared packet utilities
- `logs/`: Measurement logs, ignored by Git
- `captures/`: Raw IQ capture files, ignored by Git

## Main Parameters

- Sample rate: 10 MHz
- ZC length: 839
- Request ZC root: 25
- Response ZC root: 31
- Reply delay: 5 ms
