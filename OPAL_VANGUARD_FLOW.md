# Opal Vanguard: Modular FHSS Messaging System
## Full System Architectural Flow & Technical Specification

---

## 1. System Overview
Opal Vanguard is a high-fidelity GNU Radio implementation of a Frequency Hopping Spread Spectrum (FHSS) messaging system with multi-layer protection.

### Core Technical Specs:
*   **Sample Rate:** 10 MHz (Simulation) / 2 MHz (Hardware Target)
*   **Modulation:** GFSK (Modulation Index $h=1.0$, $BT=0.35$)
*   **DSSS Spreading:** 11-chip Barker Code (Toggleable)
*   **FEC:** Reed-Solomon (15, 11) over GF(16)
*   **Interleaving:** 8-row Matrix Interleaver
*   **Config System:** Unified `config.yaml` control

---

## 2. Advanced Signal Enhancements

### A. Matrix Interleaving
*   **Logic:** Spreads symbols across multiple FEC blocks using an 8-row matrix.
*   **Result:** Converts a massive 5-byte "burst" of interference into single-nibble errors that the RS-FEC can easily repair.

### B. Direct Sequence Spread Spectrum (DSSS)
*   **Logic:** Every bit of the payload is multiplied by an 11-chip sequence (`[1, 1, 1, -1, -1, -1, 1, -1, -1, 1, -1]`).
*   **Receiver:** The depacketizer uses a **Correlator**. It sums the product of the incoming chips and the known Barker code. If the sum is high, it's a `1`; if it's low, it's a `0`.
*   **Benefit:** Provides **Processing Gain**. The signal can be recovered even if it is significantly below the noise floor (Stealth/LPD).

---

## 3. Configuration & Control
The system is entirely modular. By editing `config.yaml`, the operator can:
*   Enable/Disable FEC, DSSS, and Interleaving independently.
*   Adjust Hopping parameters (dwell time, channel spacing).
*   Fine-tune GFSK physical layer settings.

---

## 4. The Data Flow (Complete Chain)
1.  **Session:** Buffers and Handshakes.
2.  **FEC:** Adds redundancy.
3.  **Interleave:** Shuffles symbols.
4.  **Whiten:** Scrambles for DC balance.
5.  **DSSS:** Spreads payload for stealth (Preamble/Sync remain unspread for initial lock).
6.  **GFSK:** Modulates chips/bits to RF.
7.  **FHSS:** Digital rotation hops the signal across 50 channels.
