# Opal Vanguard: Modular FHSS Messaging System
## Full System Architectural Flow & Technical Specification

Opal Vanguard is a high-fidelity GNU Radio implementation of a Frequency Hopping Spread Spectrum (FHSS) messaging system with multi-layer signal protection.

---

## 1. System Overview
The system is designed for Electronic Warfare (EW) training, allowing operators to ramp up signal hardening layers to combat noise, jamming, and manipulation.

### Core Technical Stack:
*   **Modulation:** Dual-Mode support for **GFSK** (Non-coherent frequency shift) and **DBPSK** (Differential phase shift).
*   **Hopping:** AES-CTR Counter-based frequency hopping (TRANSEC).
*   **Sync:** Dual-Mode (Asynchronous SYN/ACK or Precision TOD-Sync).
*   **Configuration:** Tiered mission control via YAML files in `mission_configs/`.

---

## 2. Signal Hardening Layers (Top to Bottom)

### Layer 1: Error Detection (CRC16 / CRC32)
*   Provides the final validation of packet integrity.
*   Located at the tail of the data block.

### Layer 2: Error Correction (Reed-Solomon 15,11)
*   Corrects up to 2 symbol errors per 15-symbol block.
*   Fundamental protection against random bit flips in the channel.

### Layer 3: Burst Resilience (Matrix Interleaving)
*   Shuffles symbols in an 8-row matrix before transmission.
*   Spreads a concentrated "burst" of noise across multiple FEC blocks, preventing block-level failure.

### Layer 4: DC Balance (Whitening & Manchester)
*   **Whitening:** Scrambles data using an $x^7+x^4+1$ LFSR.
*   **Manchester Encoding:** (Optional) Ensures a transition for every bit (1 -> 10, 0 -> 01) for perfect DC balance and clock synchronization at the cost of 50% data rate.

### Layer 5: Phase Resilience (NRZ-I)
*   Differential encoding that represents data as transitions rather than absolute values.
*   Provides immunity to 180-degree phase inversions often found in hardware FM discriminators or PSK receivers.

### Layer 6: Stealth & Processing Gain (DSSS)
*   Payload bits are multiplied by a high-speed 31-chip M-sequence.
*   **Processing Gain:** Allows the receiver to recover signals buried under the noise floor through correlation.

---

## 3. Data Flow (TX Chain)
1.  **Session:** Buffers PDU and initiates handshake if required.
2.  **FEC:** Encodes data into Reed-Solomon blocks.
3.  **Header:** Assembles Type, Length, and CRC.
4.  **Interleave:** Shuffles the full data block.
5.  **Whiten:** Scrambles the block for spectral density.
6.  **NRZ-I:** Encodes differentially.
7.  **Manchester:** (Optional) Encodes for DC balance.
8.  **DSSS:** Spreads payload bits into high-speed chips.
9.  **Modulation:** Modulates bits/chips to complex baseband (GFSK or DBPSK).
10. **FHSS:** Digital rotation (or USRP tuning) hops the signal across the band.

---

## 4. Diagnostics & Dashboard
The system provides a real-time "Health Dashboard" via the `diagnostics` message port:
*   **CRC Status:** Green/Red pass-fail indicator.
*   **FEC Correction Counter:** Real-time count of symbols repaired by Reed-Solomon.
*   **Inversion Alert:** Detects and flags inverted bitstreams.
