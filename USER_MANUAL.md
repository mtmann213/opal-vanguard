# Opal Vanguard: Master Mission Manual & Technical Guide (v12.0)

This document serves as the comprehensive user manual, participant handbook, and technical reference for the Opal Vanguard project. It is designed for operators, Red/Blue team competitors, and software developers evaluating the codebase.

---

## 📖 1. Mission Overview & Philosophy
Opal Vanguard is a **Tactical Data Link (TDL)** system designed for resilient, secure, and stealthy communications in contested RF environments. It is a software-defined "Digital Duel" platform that scales from simple GFSK links to the complex (WIP) **Differential-Frequency OFDM**.

### 🛡️ The Philosophy
- **Modular Integrity**: Every layer of the OSI model (Physical to Application) is decoupled and mission-controlled via YAML configurations.
- **Resilience by Design**: We assume the link will be jammed. We use **Reed-Solomon FEC**, **Matrix Interleaving**, and **CCSK Spreading** to ensure data survives even when the signal-to-noise ratio is negative.
- **Zero-Trust Synchronization**: Using **Time-of-Day (TOD)** hopping, radios find each other autonomously without needing a vulnerable "Sync Channel."

---

## 📡 2. System Architecture & Theory of Operation

Opal Vanguard is best understood as a **Packet-Switched Network** running over a volatile, half-duplex physical medium. 

### The Life of a Packet
1. **Application Domain**: User types a message in the Qt GUI. The UI emits a signal containing a string, which is wrapped into a **PDU (Protocol Data Unit)** and sent to the **Session Manager**.
2. **Link Layer Domain (`packetizer.py`)**:
    *   **Encryption**: Data is encrypted using AES-256 CTR.
    *   **Framing**: A 4-byte header (SrcID, Type, Seq, Length) is attached.
    *   **Integrity**: A CRC16 is calculated over the header and payload.
    *   **FEC Encoding**: The block is passed through a **Reed-Solomon** encoder (e.g., RS(15,11) or RS(31,15)).
    *   **Hardening**: Data is interleaved (spread out) and whitened (scrambled) to prevent long strings of identical bits.
    *   **Bitstream**: The final bytes are expanded into raw bits, and a **Preamble** (clock recovery) and **Syncword** (unique signature) are prepended.
3. **Physical Domain (`usrp_transceiver.py`)**:
    *   **Modulation**: Bits enter the GFSK, BPSK, or OFDM modulator.
    *   **Tag Scaling**: A critical `packet_len` tag is attached to the stream to tell the USRP hardware exactly when to start and stop the transmitter's power amplifier.
    *   **RF Emission**: Samples are streamed over USB 3.0 to the SDR and transmitted over the air.

### The "Blind Search" Engine (`depacketizer.py`)
Because the system is "Zero-Header" (no standard Wi-Fi MAC headers), the receiver is always in a **SEARCH** state. 
- It uses a sliding **XOR bitmask** to look for the Syncword.
- In Python 3.10+, we use `.bit_count()` to calculate the **Hamming Distance** (number of bit errors). 
- If the distance is within tolerance (e.g., `<= 4`), the state machine transitions to **COLLECT** and starts harvesting bits.

---

## 🚀 3. Quick Start & Deployment

### Hardware Prerequisites
- **USRP B205mini / B210** (USB 3.0 required).
- **30dB SMA Attenuators** (Mandatory for bench testing to prevent hardware damage).
- **Sync Clocks**: Host system clocks must be synchronized within 50ms for TOD-Hopping (run `ntpdate` or check system time).

### Launch Sequence
1.  **Initialize Hardware**: Verify your USRP is connected via USB 3.0.
    ```bash
    uhd_find_devices
    ```
2.  **Launch ALPHA (Master)**:
    ```bash
    sudo -E python3 src/usrp_transceiver.py --role ALPHA --serial <SERIAL_A> --config mission_configs/level1_soft_link.yaml
    ```
3.  **Launch BRAVO (Slave)**:
    ```bash
    sudo -E python3 src/usrp_transceiver.py --role BRAVO --serial <SERIAL_B> --config mission_configs/level1_soft_link.yaml
    ```

---

## 🐳 4. Docker & Air-Gapped Deployment

Containerizing the environment ensures you avoid OS-level dependency conflicts. The `Dockerfile` uses Ubuntu 22.04, GNU Radio 3.10, and UHD drivers.

### Building & Running (Online)
```bash
docker build -t opal-vanguard .
xhost +local:docker  # Allow GUI display on the host
docker-compose run --rm opal-vanguard bash
```

### Offline Transfer (Air-Gapped)
1.  **Export**: On the online PC, save the image: `docker save opal-vanguard | gzip > opal_vanguard_offline.tar.gz`
2.  **Transfer**: Copy the tarball and source code to a USB drive.
3.  **Import**: On the offline PC, load the image: `docker load < opal_vanguard_offline.tar.gz`

---

## 🛠️ 5. Mission Configuration Guide (YAML)

The system is entirely **Config-Driven**. A single YAML file defines the Physical, MAC, and Link layer parameters. Every option is described below:

### A. Physical Layer (`physical`)
| Parameter | Type/Range | Description |
| :--- | :--- | :--- |
| `modulation` | `[GFSK, MSK, GMSK, DQPSK, OFDM]` | Base modulation scheme. GFSK is standard; MSK/GMSK for high spectral efficiency; DQPSK for 2x throughput. |
| `samp_rate` | `200k to 56M` | SDR sample rate in Hz. Standard is `2000000` (2.0 Msps). |
| `center_freq`| `50M to 6G` | Base frequency in Hz. Opal Vanguard uses `915000000` (ISM band). |
| `sps` | `2 to 100` | Samples Per Symbol. Factor of interpolation/decimation. |
| `freq_dev` | `5k to 500k` | Frequency deviation for GFSK modulation in Hz. |
| `ghost_mode` | `[true, false]` | Disables the TX amplifier between bursts for stealth (LPI/LPD). |

### B. Link Layer (`link_layer`)
| Parameter | Type/Range | Description |
| :--- | :--- | :--- |
| `frame_size` | `16 to 1024` | Total packet size in bytes. Level 7 uses `940`+ for broadband. |
| `use_fec` | `[true, false]` | Enables Reed-Solomon Forward Error Correction. |
| `fec_type` | `[RS1511, RS3115]` | `RS1511` is standard; `RS3115` is heavy-duty tactical FEC. |
| `use_interleaving`| `[true, false]`| Matrix Interleaver. Spreads data to survive burst jammers. |
| `interleaver_rows`| `Quantitative` | Must divide `frame_size` evenly (e.g., 15 for 120-byte frames). |
| `use_whitening` | `[true, false]` | LFSR scrambling to balance DC offset in hardware. |
| `use_nrzi` | `[true, false]` | Differential encoding. Immune to 180-degree phase flips. |
| `use_comsec` | `[true, false]` | AES-256 CTR link-layer encryption. |
| `comsec_key` | `32-byte Hex` | Master key for data encryption. |
| `crc_type` | `[CRC16, CRC32]` | `CRC16` for L1-5; `CRC32` for high-speed OFDM (L7). |

### C. MAC Layer (`mac_layer`)
| Parameter | Type/Range | Description |
| :--- | :--- | :--- |
| `amc_enabled` | `[true, false]` | Adaptive Modulation and Coding (automatic sensitivity tuning). |
| `arq_enabled` | `[true, false]` | Automatic Repeat Request. Enables SYN/ACK handshaking. |
| `max_retries` | `0 to 10` | Number of retransmission attempts before link drop. |
| `afh_enabled` | `[true, false]` | Adaptive Frequency Hopping. Blocks jammed channels from the hop pool. |

### D. Hopping Layer (`hopping`)
| Parameter | Type/Range | Description |
| :--- | :--- | :--- |
| `enabled` | `[true, false]` | Global toggle for Frequency Hopping Spread Spectrum. |
| `type` | `[AES]` | Cryptographic pseudo-random sequence generator. |
| `sync_mode` | `[TOD]` | Time-of-Day synchronization (requires system clock sync). |
| `dwell_time_ms`| `50 to 5000` | Milliseconds spent on each frequency channel. |
| `aes_key` | `32-byte Hex` | Cryptographic seed for the hop sequence generator. |
| `num_channels` | `2 to 200` | Size of the frequency pool used for hopping. |
| `channel_spacing`| `Hz` | Gap between hopping channels (e.g., `150000`). |

### E. DSSS Layer (`dsss`)
| Parameter | Type/Range | Description |
| :--- | :--- | :--- |
| `enabled` | `[true, false]` | Global toggle for Direct Sequence Spread Spectrum. |
| `type` | `[Barker, CCSK]`| `Barker` (11-chip) or `CCSK` (32-chip tactical mapping). |
| `spreading_factor`| `Quantitative` | Number of chips used to spread each information bit. |

### F. Hardware (`hardware`)
| Parameter | Type/Range | Description |
| :--- | :--- | :--- |
| `args` | `String` | UHD device arguments (e.g., `type=b200`). |
| `tx_gain` | `0 to 90` | Transmit power in dB. |
| `rx_gain` | `0 to 90` | Receive sensitivity in dB. |
| `tx_antenna` | `String` | Physical SMA port for TX (e.g., `TX/RX`). |
| `rx_antenna` | `String` | Physical SMA port for RX (e.g., `TX/RX`). |

---

## ⚔️ 6. The Digital Duel: Red vs. Blue Team

This project features a ramping "Digital Duel" EW competition.

### Blue Team (The Operators)
*   **Objective**: Maintain a reliable link with zero CRC failures.
*   **Tactics**: Transition through the mission levels to harden your signal. If you see "FEC Repairs" increasing, your link is under attack but surviving. 
*   **Adaptive Resilience**: If the MAC layer detects 5 consecutive failures, it will automatically execute a **Fallback Reboot** to a lower, more resilient tier.

### Red Team (The Disruptors)
*   **Objective**: Deny, degrade, or manipulate the Blue Team's communication.
*   **Tools**: Use `sudo -E python3 src/adversary_jammer.py --serial <SERIAL> --mode NOISE --gain 75`. Modes include `NOISE`, `SWEEP`, `PULSE`, and `FOLLOWER`.
*   **Tactics**: Don't just jam data; attack the **Syncword** or the **Handshake** (SYN/ACK). A wideband noise floor is harder to hide from, while swept tones can push demodulators out of lock.

### The Ramping Challenge Levels
| Level | Name | Hardening | Red Team Objective |
| :--- | :--- | :--- | :--- |
| **L1** | Soft Link | None (Basic GFSK) | **Denial of Service** (Noise mode) |
| **L2** | Repairable | RS(15,11) FEC | **Burst Jamming** (Pulse mode) |
| **L3** | Resilient | FEC + Interleaving | **Saturation** (High gain) |
| **L4** | Stealth | DSSS Spreading + Ghost Mode | **Wideband Interference** (Sweep mode) |
| **L5** | Blackout | AES + TOD Hopping | **Manipulation** (Attack the sync logic) |
| **L6** | Link-16 | CCSK 32-chip + RS(31,15) | **Total Denial** (Massive wideband noise) |
| **L7** | OFDM Master | [WIP - EXPERIMENTAL] | **Surgical Strike** (In Development) |
| **L8** | Advanced | MSK / GMSK / DQPSK | **Efficiency** (Maximum spectral density) |

---

## 🔧 7. Range Setup & Hardware Upgrade Path

### RF Configuration (The "Star" Topology)
To allow the Red Team to perform "Reactive Jamming" (sniffing and injecting), use a 3-way splitter:
```text
[BLUE ALPHA TX] ---- [30dB Attenuator] ---- [SPLITTER PORT 1]
[RED JAMMER TRX] --- [30dB Attenuator] ---- [SPLITTER PORT 2] (Sniffer/Injector)
[BLUE BRAVO RX] ---- [30dB Attenuator] ---- [SPLITTER PORT 3]
```

### Hardware Upgrade Path
1. **Budget**: 915MHz SAW Bandpass Filters (~$25) to block LTE/WiFi noise.
2. **Professional**: Leo Bodnar Dual GPSDO (~$180) to provide a 10MHz reference and 1PPS signal for nanosecond-accurate TOD hopping. Yagi-Uda Antennas for spatial filtering.
3. **Lab Grade**: Ettus OctoClock-G (~$1,500) and USRP B210s for phase-coherent MIMO, beamforming, and Angle of Arrival (AoA) tracking.

---

## 📚 8. Technical Glossary
- **FHSS (Frequency Hopping Spread Spectrum)**: Rapidly switching carriers based on an AES pseudo-random sequence to evade jamming.
- **DSSS (Direct Sequence Spread Spectrum)**: Spreading signal power into the noise floor using chips, making it resistant to narrow-band interference (LPI/LPD).
- **CCSK (Cyclic Code Shift Keying)**: A modern tactical spreading technique used in Link-16.
- **COMSEC (AES-CTR)**: Counter mode encryption is used because it is "error-tolerant." A single RF bit flip only corrupts one character, not the whole block.
- **NRZI (Non-Return-to-Zero Inverted)**: Maps binary signals to state *changes*, making the link immune to 180-degree phase inversions caused by multipath.

---

## 🛠️ 9. Troubleshooting
| Issue | Potential Cause | Solution |
|-------|----------------|----------|
| Blank Waterfall | USRP Stall / USB Hub | Restart the script; ensure USRP is on a USB 3.0 port. |
| Solid Yellow Waterfall | Gain Saturation | Lower the **RX Gain** slider immediately to avoid ADC clipping. |
| [CRC FAIL] Logs | High Noise / Multipath | Increase **TX Gain** or enable Interleaving (Level 3+). |
| Decryption failed | Key Mismatch / High BER | Ensure `comsec_key` matches in YAML; lower gain to reduce saturation. |
| Status stays IDLE | Clock Drift | Run `ntpdate` or check system time sync on both laptops. |
| Topology Crash | Tag Scaling Mismatch | Ensure the `packet_len` tag logic matches the SPS of your modulator. |

---
*Opal Vanguard System Documentation | Prepared for Software Engineering Evaluation & Tactical Operation*
