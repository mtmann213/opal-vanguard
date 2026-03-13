# Opal Vanguard: Strategic Roadmap & Future Frontiers

This document outlines the detailed engineering plans for the next four phases of the Opal Vanguard project. These phases focus on scaling from a point-to-point link to a resilient, high-speed tactical network.

---

## 🌐 Phase 13: The TDMA Mesh Network (Scaling)
**Objective**: Transition from a point-to-point asynchronous link to a multi-node network using Time-Division Multiple Access (TDMA).

### 🛠️ Implementation Strategy:
1.  **The Slot Engine**: 
    *   Divide the 1-second Unix Epoch into 128 "Tactical Slots" of **7.8125ms** each (Link-16 Standard).
    *   Nodes calculate their current slot using: `(Current_Time_MS % 1000) / 7.8125`.
2.  **Node Mapping**:
    *   Update `mission_configs` to include a `node_id` and `assigned_slots` list.
    *   **ALPHA (Master)**: assigned to Slots 0, 4, 8, 12...
    *   **BRAVO (Slave)**: assigned to Slots 1, 5, 9, 13...
3.  **The Gated Transmitter**:
    *   Modify `session_manager.py` to buffer all outgoing PDUs.
    *   Implement a "Gatekeeper" that only releases a PDU to the radio if `current_slot` is in the `assigned_slots` list.
4.  **Network Discovery**: 
    *   Create a "Discovery Slot" where new nodes (e.g., CHARLIE) can broadcast a SYN to request entry into the mesh.

---

## 🧠 Phase 14: Cognitive Radio & Active AFH (EW)
**Objective**: Implement autonomous spectrum sensing to evade active jammers in real-time.

### 🛠️ Implementation Strategy:
1.  **The Spectrum Scrubber**:
    *   Add a secondary background FFT block to `usrp_transceiver.py` that monitors the *entire* 2.0 MHz hopping band.
    *   Calculate the average noise floor (dB) for every channel in the hop pool.
2.  **Autonomous Blacklisting**:
    *   If a channel's energy exceeds the floor by >15dB for 3 consecutive samples, mark it as **JAMMED**.
    *   The sensing node broadcasts an encrypted `TYPE_CTRL_EVADE` packet containing the jammed channel index.
3.  **Dynamic Hop Pool Update**:
    *   Update `hop_generator_tod.py` to accept a message-port input that adds/removes channels from the AES generator pool mid-mission.
    *   Both radios instantly "leapfrog" the jammed frequency without losing synchronization.

---

## 🔐 Phase 15: COMSEC Hardening (Security)
**Objective**: Move beyond static keys to achieve absolute cryptographic forward-secrecy.

### 🛠️ Implementation Strategy:
1.  **Over-the-Air Rekeying (OTAR)**:
    *   Implement a `REKEY` command (Type 3). 
    *   ALPHA generates a 256-bit random Session Key, encrypts it with the **Master Key** (from YAML), and sends it to BRAVO.
    *   Once BRAVO sends a `REKEY_ACK`, both radios switch their `packetizer` and `depacketizer` to the new key.
2.  **Anti-Replay Protection**:
    *   Implement a **Rolling Nonce Window**. 
    *   Every packet must have a Sequence Number greater than the last received packet.
    *   If an adversary records a "BFT" packet and tries to re-broadcast it later, the receiver will reject it as a "Replay Attempt."
3.  **Key Zeroization**: 
    *   Add a "Panic Button" to the TOC GUI that instantly wipes all keys from memory and resets the radio to IDLE.

---

## 🚀 Phase 16: Phase-Coherent OFDM (Broadband)
**Objective**: Stabilize Level 7 to support 512kbps+ tactical video or audio streams.

### 🛠️ Implementation Strategy:
1.  **The Syncword Upgrade**: 
    *   Replace the current bit-based sync with **Schmidl & Cox** preamble detection.
    *   Use two identical symbols at the start of every OFDM burst to allow the receiver to calculate **Carrier Frequency Offset (CFO)**.
2.  **Phase Transition Correction**:
    *   Implement **Differential-Frequency (DF-OFDM)** mapping where information is carried in the phase difference *between* carriers, making it immune to the global phase shifts caused by frequency hopping.
3.  **Pilot-Aided Equalization**: 
    *   Insert "Pilot Tones" at fixed carrier positions (e.g., carriers -21, -7, 7, 21). 
    *   The receiver uses these tones to "twist" the incoming signal back into alignment, compensating for RF fading in real-time.

---

## 📋 Tactical Backlog & Research Bin
*This section serves as a living backlog for high-value features and research topics identified during development but reserved for future consideration.*

### 🎙️ A. Low-Bitrate Tactical Voice
*   **Concept**: Integrate **Codec2** (3200 bps) to support digital voice over the hopping link.
*   **Value**: Provides secure, jam-resistant voice comms within the existing GFSK/MSK framework.

### 📡 B. Passive Signal Intelligence (SIGINT)
*   **Concept**: Use the "Spectrum Scrubber" from Phase 14 to not just evade jammers, but to log and identify enemy transmitter types based on their spectral fingerprint.
*   **Value**: Transforms the radio into a situational awareness sensor.

### 📱 C. Web-Based Remote Dashboard
*   **Concept**: Add a lightweight Flask/WebSocket bridge to allow the TOC to be viewed on a tablet or mobile device over a local network.
*   **Value**: Unlocks "Handheld" situational awareness for operators in the field.

### ⚡ D. FPGA-Offload Acceleration
*   **Concept**: Move the Syncword correlator and AES-Hop generator into Verilog (RFNoC) for the USRP.
*   **Value**: Enables "True" Link-16 hopping speeds (12,000+ hops/sec) by eliminating USB latency.

### 📡 E. Advanced Waveform Suite
*   **CSS (Chirp Spread Spectrum)**: Implement LoRa-style swept-frequency chirps for ultra-resilient communication below the noise floor.
*   **OQPSK (Offset QPSK)**: Optimize DQPSK for USRP hardware by offsetting I/Q channels, ensuring a constant envelope and cleaner bursts.
*   **8PSK / D8PSK**: A "Throughput Tier" modulation encoding 3 bits/symbol for high-SNR broadband environments.
*   **CPM (Continuous Phase Modulation)**: The "Military Master" waveform. A generalization of GMSK using Viterbi decoding for maximum spectral efficiency.
*   **Tactical QAM (16/64-QAM)**: Reserved for **Phase 16 (Broadband)**. Suitable for high-bandwidth terrestrial backhaul (Microwave/Link-22) but requires strict amplifier linearity.

---
*Roadmap generated for Opal Vanguard v15.0. These frontiers represent the path to a Tier-1 Tactical Data Link.*

## 🛰️ Phase 33: Multiprocessing Offload (Performance Target)
**Objective**: Solve the "Progressive Stutter" in Level 6.
- **The Strategy**: Move the Reed-Solomon (RS-FEC) and Matrix Deinterleaving logic into a dedicated Python Process instead of a Thread. 
- **The Benefit**: By decoupling the heavy mathematical "Link Layer" from the high-speed "Physical Layer," we ensure the Waterfall and USRP Sink never run dry, even when correcting maximum bit errors.
- **Target Modulation**: High-speed multi-carrier OFDM (Level 7) and 128-chip CCSK (Level 6).
