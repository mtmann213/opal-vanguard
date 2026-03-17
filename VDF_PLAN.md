# Mission Plan: Vanguard Data Factory (VDF)
**Objective:** Capture 500,000+ synchronized I/Q snapshots using the Hardware Trinity (3x USRP B205-mini) to create a high-fidelity, environment-aware training dataset for the `ai-rf` ResNet.

## 1. Modulation Requirements
We will target the "Trinity Suite," which includes all 24 modulations from the 2018.01A dataset, plus 6 "Vanguard-Specific" classes for real-world robustness and modern standard awareness.

*   **Digital PSK/APSK Suite:** BPSK, QPSK, 8PSK, 16PSK, 32PSK, 16APSK, 32APSK, 64APSK, 128APSK, OQPSK.
*   **Quadrature (QAM) Suite:** 16QAM, 32QAM, 64QAM, 128QAM, 256QAM.
*   **Amplitude (ASK/OOK) Suite:** OOK, 4ASK, 8ASK.
*   **Analog Suite:** AM-SSB-WC, AM-SSB-SC, AM-DSB-WC, AM-DSB-SC, FM.
*   **Modern Standards (Vanguard Expansion):**
    *   **GMSK** (Used in GSM/AIS).
    *   **OFDM** (The backbone of WiFi, LTE, and 5G).
    *   **LoRa** (Chirp Spread Spectrum for IoT).
    *   **FSK/GFSK** (Used in Bluetooth and industrial telemetry).
*   **Signal Environment Classes:** 
    *   **Pure Noise** (Capture of the local RF floor).
    *   **Active Jamming** (Output of the BPSK-Jammer logic).

## 2. Signal Construction Strategy
To make the AI robust, the signals must be transmitted in two distinct modes:

### A. Random Symbol Mode (70% of Dataset)
*   **Purpose:** Teaches the AI the "Physics" of the modulation (the constellation shape).
*   **Method:** Generate purely random bitstreams and map them to symbols.
*   **Benefit:** Prevents the AI from "cheating" by learning a specific recurring data pattern.

### B. Framed Packet Mode (30% of Dataset)
*   **Purpose:** Teaches the AI the "Structure" of real radio comms.
*   **Method:** Include standard preambles, sync words, and header structures.
*   **Benefit:** Helps the AI identify signals even when the payload is silent or zeroed out.

## 3. Environment & Interference Matrix
Using the 3rd USRP as an **Adversary Node** is critical.

*   **SNR Control:** Vary the TX gain from 0dB to 60dB to simulate distance.
*   **The Adversary Node (USRP #3):**
    *   **Adjacent Channel Interference:** Transmit high-power BPSK signals 1MHz away.
    *   **In-Band Jamming:** Intermittently transmit noise bursts on top of the target.
*   **Multipath Simulation:** Vary RX placement to capture real-world echoes.

## 4. Technical Requirements & Dataset Scale
*   **Sample Rate:** 1 Msps (Standard) or 5 Msps (High-Res).
*   **Snapshots per Class:** 20,000 snapshots.
*   **Snapshot Shape:** `(1024, 2)` (I and Q channels).
*   **Total Dataset Size:** ~25GB (HDF5 format).
*   **Storage Path:** Results stored in `data/vdf_captures/` (Ignored by Git).
*   **Hardware Serials (The Trinity):**
    *   **TX Node:** `3449AC1`
    *   **RX Node:** `3457464`
    *   **Adversary Node:** `3457480`
*   **Synchronization (Anti-Drift):** 
    *   Inject a **10ms Pilot Tone** (CW at offset) at the start of every modulation change. 
    *   The Receiver must detect this tone to reset the sample counter, ensuring labels never "drift" due to network/USB lag.
*   **Hardware Diversity:** 
    *   Capture 50% of data via **SMA Coaxial Cables** (Clean Reference).
    *   Capture 50% of data via **Antennas** (Real-World Multipath).
*   **Spectral Diversity (Frequency Sweep):**
    *   Capture samples across three distinct bands: **433 MHz** (UHF), **915 MHz** (Mid-Band), and **2.45 GHz** (ISM).
*   **Temporal Diversity (Symbol Rate):**
    *   Vary the **Samples Per Symbol (SPS)** across 4, 8, and 16 to ensure the ResNet is scale-invariant.
*   **Sigma Hardening (Hardware Impairments):**
    *   **Carrier Frequency Offset (CFO):** Intentionally offset the TX by ±5 kHz.
    *   **Sample Clock Offset (SCO):** Inject tiny timing skews.
    *   **Pulse Shaping Variation:** Vary filter roll-off (Alpha) between 0.2 and 0.5.
*   **Operational Requirements:**
    *   **Hardware Warm-up:** Dummy TX for 5 minutes before capture to stabilize oscillators.
    *   **Inter-Burst Gaps:** Include "Signal Edges" in 10% of snapshots (signal starting/stopping mid-window).
    *   **Ground Truth Metadata:** Every HDF5 entry must include a linked metadata record of the exact SNR, CFO, SCO, and SPS used for that specific sample.

## 5. Development Roadmap (The "Data Factory" Branch)

### Phase 0: The VDF Pilot (MANDATORY)
Before the full 25GB run, perform a "Small-Scale Test Flight":
1.  **Scope:** 2 Modulations (BPSK, FM) | 1,000 snapshots each.
2.  **Verify:** HDF5 structure compatibility and Label Reconstruction accuracy.
3.  **Benchmarking:** Run Stage 1 of the Acclimation Strategy on this Pilot data.

### Phase 1: The Sequencer (`src/vdf_sequencer.py`)
2.  **The Labeler (`src/vdf_labeller.py`):** Implements a hard-coded tagging engine to ensure labels are never corrupted.
3.  **The Sionna Bridge:** Pre-calculates waveforms to ensure mathematical purity before hardware impairments are added by the radio.

---
### **Transfer Learning Integration**
Once the VDF dataset is generated, the `ai-rf` project will perform **Transfer Learning**:
1.  Load `best_resnet_v7.keras`.
2.  Freeze early convolutional layers.
3.  Fine-tune on the physical USRP data to adapt the "Simulated Brain" to the "Hardware Realities."
