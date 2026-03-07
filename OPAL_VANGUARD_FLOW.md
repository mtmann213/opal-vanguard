# Opal Vanguard: Development Retrospective & Architecture Evolution

This document traces the technical journey of the Opal Vanguard project, documenting the major challenges, "Smoking Guns," and the definitive fixes that led to the v8.2 stable baseline.

---

## 🛡️ Milestone 1: The Burst Timing Crisis
**Symptoms**: USRP T/R switches "clipping" the start of packets; `check_topology` scheduler crashes.
- **Discovery**: GNU Radio hierarchical modulators (like `gfsk_mod`) were "Tag Black Holes"—they consumed the `packet_len` tags but didn't pass them to the USRP, leaving the hardware "deaf" or "blind" to burst boundaries.
- **The Fix**: Rebuilt the modulator using raw primitives (Gaussian Filter + Frequency Modulator) that preserve tags. Implemented a custom `BurstTagger` to explicitly inject `tx_sob` and `tx_eob` tags.

## 📡 Milestone 2: The DSSS Physics Trap
**Symptoms**: Blank waterfalls at high sample rates; sporadic heartbeats; "blurry" Inspectrum signals.
- **Discovery**: Work backward from the channel width! We found that a DSSS Spreading Factor of 31 was expanding our 100kbps signal to 6.3 MHz—physically impossible to fit in 200kHz channels or a 5MHz capture window.
- **The Fix**: Standardized on the "Winning Baseline": 1 Msps / 2 Msps sample rates, SPS of 10, and a narrow 25kHz deviation. This kept the signal "sharp" and perfectly contained within the mission-alloted spectrum.

## 🔐 Milestone 3: The COMSEC Deadlock
**Symptoms**: `Decryption failed` errors; handshake loops; heartbeats not appearing despite good sync.
- **Discovery A**: The Packetizer was calculating the header length *before* encryption added its nonce/tag overhead. The header was "lying" about the packet size.
- **Discovery B**: AES-GCM is "fragile." A single flipped bit in the air causes the entire packet to be discarded.
- **The Fix**: Refactored to **AES-CTR** (Stream Cipher) for bit-error tolerance. Standardized the encryption sequence so the header is packed *after* the payload is fully secured. Restricted encryption to DATA packets only to ensure the initial SYN/ACK handshake is never blocked.

## 📊 Milestone 4: Diagnostic Visibility
**Symptoms**: Hard to tune gains; difficulty verifying bit-level recovery.
- **The Fix**: Implemented the **Signal Scope** in the GUI. Added a 64-bit "Early Trigger" so the scope centers on the syncword while showing the preamble history. This allows the operator to see exactly how "clean" the recovered bits are in real-time.

## 🧪 Milestone 5: The Safeguard Baseline
**Symptoms**: Fear of regressions when moving to higher levels (Level 6/7).
- **The Fix**: Created `verify_mission_baseline.py`. This provides a pure digital loopback test for Levels 1-5, ensuring that any future architectural changes for Link-16 (Level 6) don't break the already "won" missions.

---

## 🏆 Current "Golden State" (v8.2)
- **Modulation**: GFSK (Standard) / DBPSK (Tactical).
- **Architecture**: Asynchronous PDU-based handshaking with SOB/EOB tagging.
- **Sync**: 0x3D4C5B6A with 2-bit Hamming tolerance.
- **Encryption**: AES-CTR (Error-resilient).
- **Timing**: TOD-Synced Hardware Retuning (1 second dwell).
