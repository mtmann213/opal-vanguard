# Opal Vanguard: Full Project Chronicle & Technical Evolution

This document serves as the complete technical history of the Opal Vanguard project, from its inception as a GNU Radio experiment to a resilient, military-grade tactical transceiver.

---

## 🌑 Phase 0: The GRC Foundations (Initial Commits)
**Focus**: Proving the "Big Three" (FHSS, Whitening, FEC).
- **The Concept**: Use a Fibonacci LFSR for hopping and a primitive Reed-Solomon block for error correction.
- **Challenge**: Initial designs were locked inside `.grc` (GNU Radio Companion) files, making them difficult to automate or tune for real-world hardware.
- **The Pivot**: Decoupled the logic into pure Python `gr.basic_block` components (`packetizer.py`, `depacketizer.py`) to allow for dynamic, mission-driven configuration.

## 🏗️ Phase 1: The Handshake & Session Management
**Focus**: Solving the "Finding each other" problem.
- **Milestone**: Implementation of the **Seed Sync**. Before this, both radios had to be started at the exact same millisecond to stay in the same hop sequence.
- **The Solution**: Created `session_manager.py`. Introduced the **SYN -> ACK** handshake. Node A broadcasts a clear-text SYN containing its current LFSR seed; Node B locks onto it and replies ACK.
- **Refinement**: Added thread-safe GUI signals to prevent the handshake from freezing the UI.

## 🛡️ Phase 2: Signal Hardening (The "EW" Era)
**Focus**: Resilience against active jamming.
- **Milestone**: Added **Matrix Interleaving** and **NRZ-I**. 
- **Discovery**: Found that burst jammers were killing 5-10 bits in a row, which defeated the Reed-Solomon FEC. 
- **The Fix**: Interleaving spread those 10 dead bits across the entire 120-byte packet, turning a "fatal burst" into isolated "repairable flips." Added NRZ-I to protect against the 180-degree phase inversions common in multipath environments.

## 📡 Phase 3: The USRP Migration (Hardware Pivot)
**Focus**: Moving from HackRF (Simplex) to USRP B205mini (Tactical Half-Duplex).
- **Milestone**: Ported the entire flowgraph to the **UHD (USRP Hardware Driver)**.
- **The "Tag Black Hole" Crisis**: Discovered that hierarchical GNU Radio blocks were deleting the burst-timing tags. This led to the **"Tag-Safe Refactor"**, where the modulator was rebuilt from raw primitives (Gaussian Filter + FM Modulator) to ensure the USRP hardware knew exactly when to flip its T/R switch.

## 🔐 Phase 4: Cryptographic Synchronization
**Focus**: Authenticated Hopping and COMSEC.
- **Milestone**: Replaced the simple LFSR hop generator with a cryptographically secure **AES-CTR Generator**.
- **The TOD Pivot**: Introduced **Time-of-Day (TOD)** synchronization. Radios no longer need a clear-text handshake to find each other; they use the absolute Unix epoch time to land on the same frequency automatically.
- **Encryption Evolution**: Transitioned from AES-GCM (fragile in RF) to **AES-CTR** (error-tolerant) to ensure heartbeats survive minor interference without crashing the security layer.

## 📊 Phase 5: The Diagnostic Milestone (v8.1+)
**Focus**: Visibility and Maintainability.
- **Visible Logic**: Implemented the **Signal Scope** with early-tag triggering. For the first time, operators could see the preamble and syncword in the time-domain to diagnose "Hardware Clipping."
- **The Safeguard**: Created `verify_mission_baseline.py`. This standardized the "Won" missions (1-5), ensuring that as we move into Level 6 (Adaptive Frequency Hopping), the fundamental radio math remains untouchable.

## ⚔️ Milestone 6: The "Link-16" Breakthrough (Level 6)
**Symptoms**: Constant CRC fails despite 90%+ confidence; `reshape` errors; "Silent" sync triggers.
- **Discovery A: The Reshape Math**: Found that matrix interleaving requires perfect integer multiples. Switched to a strict **120-byte tactical block** with a **15-row interleaver** ($120/15=8$) to ensure mathematical symmetry.
- **Discovery B: The Sync Fragility**: Found that a 64-bit strict syncword was too perfect for RF. Reverted to a **32-bit Hamming sync** (2-bit tolerance) to survive signal fading.
- **Discovery C: The Self-Healing Header**: Realized that bit-flips in the `plen` byte were causing the radio to misinterpret packet sizes. Moved the **entire header inside the FEC protection zone**, allowing the radio to "heal" its own metadata before reading it.
- **Discovery D: The Payload CRC**: Discovered that the Packetizer and Depacketizer were out of sync on what the CRC protected. Standardized on a **Full-Block CRC** (Header + Payload) for absolute structural integrity.

---

## 🏆 Final Stable State (v10.9)
| System | Implementation | Result |
|--------|----------------|--------|
| **Link-16 (L6)** | 120-byte block, 15-row Interleaver, 32-bit Sync | 100% Symmetric & Resilient |
| **FEC** | RS(15,11) Self-Healing Header & Payload | Repairs up to 2 bytes per block |
| **COMSEC** | AES-256 CTR (Error-Tolerant) | Heartbeats survive bit-flips |
| **Dashboard** | Real-time Status & Diagnostic Routing | Full operator visibility |
