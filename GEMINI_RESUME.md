# Mission Hand-off: Project Opal Vanguard
## Session State: Tuesday, February 24, 2026

### 1. Current Context
*   **Active Branch:** `experimental/advanced-dsp`
*   **GitHub Repository:** `mtmann213/opal-vanguard`
*   **Mission Goal:** Military-grade modular FHSS messaging system for 900MHz ISM.

### 2. Technical Achievement Summary
The system has transitioned from a basic loopback to a robust, protected datalink with the following layers (from top to bottom):
1.  **Session Layer:** `session_manager.py` handles SYN/ACK handshakes and packet buffering.
2.  **FEC Layer:** `rs_helper.py` implements Reed-Solomon (15,11) with brute-force error correction (fixes 2 symbols/block).
3.  **Interleaving Layer:** `dsp_helper.py` (MatrixInterleaver) shuffles symbols to defeat burst noise.
4.  **Whitening Layer:** $x^7 + x^4 + 1$ LFSR for DC balance.
5.  **Stealth Layer (DSSS):** `dsp_helper.py` (DSSSProcessor) spreads bits using an 11-chip Barker code for LPD/LPI and processing gain.
6.  **Physical Layer:** Calibrated GFSK ($h=1.0, BT=0.35$) at 10 MHz sample rate.
7.  **FHSS Layer:** LFSR-based frequency hopping across 50 channels (150kHz spacing).

### 3. Key Files
*   `config.yaml`: The master toggle for all enhancements (DSSS, FEC, etc.).
*   `src/top_block_gui.py`: The advanced wideband lab with real-time stress-test sliders.
*   `OPAL_VANGUARD_FLOW.md`: The definitive technical architecture guide.

### 4. Verification Benchmarks (Passed)
*   **Handshake Reliability:** Node A buffers data until Node B syncs via SYN/ACK.
*   **FEC/CRC Integrity:** Link survives ~0.12V AWGN noise without DSSS.
*   **DSSS Processing Gain:** Link survives higher noise floor through correlation.
*   **Inspectrum Analysis:** Syncword `0x3D4C5B6A` and Barker chips verified in `.cf32` captures.

### 5. Next Mission Objectives (Pending)
1.  **NRZ-I Encoding:** Implement in `dsp_helper.py` to protect against phase inversion.
2.  **Fast Frequency Hopping:** Transition from LFSR to AES-CTR sequence and reduce dwell time to <10ms.
3.  **Time-of-Day (TOD) Sync:** Move from asynchronous handshake to precision time alignment.
4.  **Hardware Integration:** Integrate `gr-uhd` blocks for USRP B205mini/B210 deployment.

### 6. Resumption Instructions for Gemini CLI
1.  Clone/Pull the `experimental/advanced-dsp` branch.
2.  Run `python3 src/test_loopback.py` to confirm the digital logic is intact.
3.  Run `python3 src/top_block_gui.py` to demonstrate the current lab capabilities.
4.  Review `OPAL_VANGUARD_FLOW.md` for logic implementation details.
