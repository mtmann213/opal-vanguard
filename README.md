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
- **/src**: Contains Python Out-Of-Tree (OOT) blocks and hardware transceiver logic (`usrp_transceiver.py`, `adversary_jammer.py`).
- **/mission_configs**: Contains tiered YAML configuration files (`level1_soft_link.yaml` to `level6_link16.yaml`) defining the datalink parameters.
- **/grc**: Contains GNU Radio Companion (GRC) block definitions (`.block.yml`) and legacy loopback flowgraphs.

## Quick Start

### 1. Hardware Field Test (USRP B200/B205mini)
To run a physical RF test between two USRPs, use the transceiver script and point to a specific difficulty level:
```bash
# Terminal 1 (Alpha)
sudo -E python3 src/usrp_transceiver.py --role ALPHA --serial <SERIAL_1> --config mission_configs/level1_soft_link.yaml

# Terminal 2 (Bravo)
sudo -E python3 src/usrp_transceiver.py --role BRAVO --serial <SERIAL_2> --config mission_configs/level1_soft_link.yaml
```

### 2. Contested Environment (Red Team)
To test the datalink's resilience against jamming, launch the adversary script on a third USRP:
```bash
sudo -E python3 src/adversary_jammer.py --serial <SERIAL_3> --mode NOISE --gain 75
```

### 3. Run Visual Demo (Simulation)
The project includes a full QT GUI flowgraph implemented directly in Python for testing without hardware:
```bash
python3 src/top_block_gui.py --config mission_configs/level4_stealth.yaml
```

## Technical Specifications
- **Spectrum:** 902-928 MHz (ISM Band)
- **Modulation:** GFSK
- **FEC:** Reed-Solomon (15, 11)
- **Hop Rate:** Variable (200ms default)
- **Platform:** GNU Radio 3.10+ (Python 3.x)

## License
Opal Vanguard is released under the **GPL-3.0-or-later** license.
