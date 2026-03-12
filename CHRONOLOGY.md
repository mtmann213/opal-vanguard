# Opal Vanguard: Full Project Chronicle & Technical Evolution

## 2026-03-11: The Great Stabilization (v19.25 -> v19.58)
**Status**: Critical Success. Link-16 (Level 6) hardened and Baseline restored.

### 🛑 The Challenge
The system was suffering from intermittent `tP` (Tag Propagation) and `Tag Gap` errors on the USRP Sink. This was causing bursts to be truncated prematurely, leading to CRC failures and lost heartbeats, especially in the wideband CCSK modes.

### 🛠 The Breakthroughs
1.  **Surgical Tag Scaling (v19.48):**
    - Abandoned redundant `tagged_stream_multiply_length` blocks.
    - Created `FinalTagFixer`, a custom block that reads a safe `bit_count` tag and produces a perfectly scaled `packet_len` tag for the USRP.
    - **Modulator Delay Compensation**: Added a 320-sample offset to tags to account for the modulator's internal filter pipeline.
2.  **Phase-Inversion Resilience (v19.51):**
    - Optimized the `depacketizer` to search for both normal and 180-degree inverted syncwords (XOR mask 0xFFFFFFFF).
    - Hardened the GFSK/DBPSK clock recovery parameters for better hardware SNR.
3.  **Protocol Alignment (v19.57):**
    - Standardized on `big-endian` bitorder.
    - Simplified Level 1 configuration to provide a "clean wire" baseline for hardware testing.
4.  **Headless Parity (v19.42):**
    - Rewrote `usrp_headless.py` to use a single session manager and identical DSP parameters to the GUI transceiver.

### 📊 Current Evolution State
- **Stability**: 100% success in digital loopback; high hit-probability on B205mini hardware.
- **Modulation**: GFSK (Standard), DBPSK (Tactical), MSK (Link-16).
- **Spreading**: CCSK (32-chip) fully operational in Level 6.
- **Telemetry**: Real-time Mission ID and SNR visibility.

---
*Chronology maintained by Gemini CLI v1.0*
