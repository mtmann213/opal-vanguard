# Opal Vanguard: Modular FHSS Messaging System

## Overview
Opal Vanguard is a Python-based GNU Radio framework for a modular Frequency Hopping Spread Spectrum (FHSS) messaging system. It implements a complete digital communication chain with Forward Error Correction (FEC), scrambling, and real-time frequency hopping control.

## Key Features
- **Frequency Hopping:** AES-CTR and TOD-based hopping across 50+ channels in the 900MHz ISM band.
- **Forward Error Correction (FEC):** Reed-Solomon (15, 11) and (31, 15) for high-reliability links.
- **Advanced Spreading:** Supports standard **DSSS** (31-chip) and authentic Link-16 **CCSK** (32-chip symbol mapping).
- **Multi-Modulation:** Support for **GFSK, MSK, DBPSK, DQPSK, D8PSK, and OFDM**.
- **Scrambling/Whitening:** Fibonacci LFSR whitening using the $x^7 + x^4 + 1$ polynomial.
- **Standardized Missions:** Tiered mission configurations (`level1` to `level7`) for progressive difficulty.

## Project Structure
- **/src**: Contains Python Out-Of-Tree (OOT) blocks and hardware transceiver logic (`usrp_transceiver.py`, `adversary_jammer.py`).
- **/mission_configs**: Contains tiered YAML configuration files (`level1_soft_link.yaml` to `level6_link16.yaml`) defining the datalink parameters.
- **/grc**: Contains GNU Radio Companion (GRC) block definitions (`.block.yml`) and legacy loopback flowgraphs.

## Quick Start

### 1. Hardware Field Test (USRP B200/B205mini)
To run a physical RF test between two separate nodes, use the transceiver script on each respective computer:
```bash
# Computer 1 (Alpha)
sudo -E python3 src/usrp_transceiver.py --role ALPHA --serial <SERIAL_1> --config mission_configs/level1_soft_link.yaml

# Computer 2 (Bravo)
sudo -E python3 src/usrp_transceiver.py --role BRAVO --serial <SERIAL_2> --config mission_configs/level1_soft_link.yaml
```

### 2. Contested Environment (Red Team)
To test the datalink's resilience against jamming, launch the adversary script on a third computer:
```bash
# Computer 3 (Jammer)
sudo -E python3 src/adversary_jammer.py --serial <SERIAL_3> --mode NOISE --gain 75
```

### 3. Run Visual Demo (Simulation)
The project includes a full QT GUI flowgraph implemented directly in Python for testing without hardware:
```bash
python3 src/top_block_gui.py --config mission_configs/level4_stealth.yaml
```

### 4. Mission Commander Dashboard (Telemetry)
The project includes a web-based dashboard for real-time mission telemetry. To launch the dashboard, run the Flask app from the `dashboard/` directory:
```bash
python3 dashboard/app.py
```
Then navigate to `http://localhost:5000` in your web browser.

## Technical Specifications
- **Spectrum:** 902-928 MHz (ISM Band)
- **Modulation:** GFSK
- **FEC:** Reed-Solomon (15, 11)
- **Hop Rate:** Variable (200ms default)
- **Platform:** GNU Radio 3.10+ (Python 3.x)

## License
Opal Vanguard is released under the **GPL-3.0-or-later** license.
