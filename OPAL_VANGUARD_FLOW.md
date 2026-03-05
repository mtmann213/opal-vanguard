# Opal Vanguard: Modular FHSS Messaging System
## Full System Architectural Flow & Technical Specification

Opal Vanguard is a high-fidelity GNU Radio implementation of a Frequency Hopping Spread Spectrum (FHSS) messaging system with multi-layer signal protection.

---

## 1. System Overview
The system is designed for Electronic Warfare (EW) training, allowing operators to ramp up signal hardening layers to combat noise, jamming, and manipulation.

### Core Technical Stack:
*   **Modulations:** GFSK, MSK, DBPSK, DQPSK, D8PSK.
*   **Hopping:** AES-CTR and TOD-based frequency hopping.
*   **Sync:** Precision TOD-Sync (Time-of-Day) for nanosecond alignment.
*   **Configuration:** Tiered mission control via YAML files in `mission_configs/`.

---

## 2. Signal Hardening Layers (Top to Bottom)

### Layer 1: Error Detection (CRC16 / CRC32)
*   Provides the final validation of packet integrity.

### Layer 2: Error Correction (RS 15,11 or RS 31,15)
*   **RS 15,11:** Standard protection against random bit flips.
*   **RS 31,15:** Military-grade protection used in Link-16 mission modes.

### Layer 3: Burst Resilience (Matrix Interleaving)
*   Shuffles data in a matrix (up to 32x32) before transmission.
*   Spreads concentrated "burst" jamming across multiple FEC blocks.

### Layer 4: DC Balance (Whitening)
*   Scrambles data using an $x^7+x^4+1$ LFSR to ensure high transition density.

### Layer 5: Phase Resilience (NRZ-I)
*   Differential encoding providing immunity to 180-degree phase inversions.

### Layer 6: Stealth & Spreading (DSSS or CCSK)
*   **DSSS:** 31-chip M-sequence spreading for processing gain.
*   **CCSK:** Cyclic Code Shift Keying (32-chip) for authentic Link-16 emulation.

---

## 3. Data Flow (TX Chain)
1.  **Application Layer:** Generates payload (Heartbeat strobe, Chat message, or FTP file chunk).
2.  **Session (MAC):** Controls state, ARQ history buffering, and AFH blacklist tracking.
3.  **COMSEC:** Encrypts payload bytes using AES-256-GCM with sequence-based nonces.
4.  **FEC:** Encodes data into Reed-Solomon blocks (5-bit or 4-bit symbols).
5.  **Header:** Assembles Type, Sequence, and Length metadata.
6.  **Interleave:** Shuffles the full data block based on mission level.
7.  **Whiten:** Scrambles the block using a synchronized LFSR.
8.  **Spreading:**
    *   **CCSK Path:** Maps 5-bit symbols directly to 32-chip sequences.
    *   **DSSS Path:** Spreads serialized bits into 31-chip sequences.
9.  **Modulation:** Converts bits/chips to complex baseband (MSK, GFSK, PSK, or OFDM).
10. **LPI/LPD Controller:** Triggers hardware "Ghost Mode" to instantly spike/cut TX power.
11. **UHD Sink:** Transmits bursts via USRP hardware with nanosecond TOD frequency control.

---

## 4. Diagnostics & Dashboard
The system provides a real-time "Health Dashboard" via the `diagnostics` message port:
*   **CRC Status:** Green/Red integrity indicator.
*   **Confidence (Conf):** Real-time correlation quality from the despreader.
*   **Inversion Alert:** Flags 180-degree phase flips in the received stream.
