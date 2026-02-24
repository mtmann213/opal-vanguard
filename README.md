# Opal Vanguard: Modular FHSS Messaging System

## Overview
Opal Vanguard is a Python-based GNU Radio framework for a modular Frequency Hopping Spread Spectrum (FHSS) messaging system. It implements a complete digital communication chain with Forward Error Correction (FEC), scrambling, and real-time frequency hopping control.

## Key Features
- **Frequency Hopping:** Fibonacci LFSR-based hopping across 50 channels in the 900MHz ISM band.
- **Forward Error Correction (FEC):** Reed-Solomon (15, 11) encoding and decoding on 4-bit nibbles.
- **Scrambling/Whitening:** Fibonacci LFSR whitening using the $x^7 + x^4 + 1$ polynomial, integrated into the packet framing.
- **GFSK Modulation:** Gaussian Frequency Shift Keying with Gaussian pulse shaping (`bt=0.35`).
- **Packet Structure:** 
  - **Preamble:** `0xAAAA`
  - **Syncword:** `0x3D4C5B6A`
  - **Length Header:** 1 byte
  - **Payload:** FEC-protected and whitened
  - **CRC16-CCITT:** For error detection

## Project Structure
- **/src**: Contains Python Out-Of-Tree (OOT) blocks (Packetizer, Depacketizer, Hop Controller, Whitener, RS Helper).
- **/grc**: Contains GNU Radio Companion (GRC) block definitions (`.block.yml`) and the full loopback flowgraph (`.grc`).

## Quick Start

### 1. Set GRC Block Path
To use the custom blocks in GNU Radio Companion, add the `grc/` directory to your configuration or set the environment variable:
```bash
export GRC_BLOCK_PATH=$(pwd)/grc
gnuradio-companion grc/opal_vanguard_loopback.grc
```

### 2. Run Interactive Demo
A standalone Python demo is provided to verify the digital logic without GRC:
```bash
python3 interactive_demo.py
```

### 3. Run Visual Demo
The project includes a full QT GUI flowgraph implemented directly in Python:
```bash
python3 src/top_block_gui.py
```

## Technical Specifications
- **Spectrum:** 902-928 MHz (ISM Band)
- **Modulation:** GFSK
- **FEC:** Reed-Solomon (15, 11)
- **Hop Rate:** Variable (200ms default)
- **Platform:** GNU Radio 3.10+ (Python 3.x)

## License
Opal Vanguard is released under the **GPL-3.0-or-later** license.
