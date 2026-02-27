# Mission Hand-off: Project Opal Vanguard (FIELD READY)
## Session State: Tuesday, February 24, 2026

### 1. Project Status: Hardware Integration Phase
Opal Vanguard is fully verified and "Field Ready." The signal chain has passed 18/18 automated configuration tests across both GFSK and DBPSK modulations. It is ready for deployment to USRP B210 / B205mini hardware.

### 2. Technical Achievement Summary
*   **PHY/Link Overhaul:** Multi-mode support for **GFSK** and **DBPSK**. Optimized for 2MHz hardware sample rate.
*   **Hardening:** 31-chip DSSS, NRZ-I, Manchester Encoding, 8-row Matrix Interleaving, and Reed-Solomon (15,11) FEC.
*   **Hopping:** AES-CTR secure TRANSEC sequence generator.
*   **Sync:** Precision TOD-Sync (Time-of-Day) for stealthy, self-healing links.
*   **Diagnostics:** Real-time "Signal Health Dashboard" with CRC and FEC monitoring.
*   **Verification:** `src/test_all_configs.py` confirms all 18 permutations pass CRC.

### 3. Primary Command Center
*   **`src/usrp_transceiver.py`**: Field-ready hardware terminal. Supports `--role ALPHA/BRAVO` and `--serial`.
*   **`src/top_block_gui.py`**: Wideband software simulation lab with 10MHz visualization and stress-test sliders.
*   **`config.yaml`**: The "Mission Manual" for all signal and hardware toggles.

### 4. Verification Benchmarks
*   **Digital Integrity:** 100% pass on 18 permutations (GFSK/DBPSK x 9 Link-Layer modes).
*   **Simulation Stress:** DSSS 31-chip mode survives >0.40V AWGN and 100% burst jamming.
*   **HW Readiness:** `firdes` Nyquist constraints resolved for 2MHz operation.

### 5. Resumption Instructions for Lab Day
1.  **Clone/Pull:** `git checkout hardware/usrp-integration`.
2.  **Verify Environment:** Ensure `uhd`, `gnuradio-pdu`, and `cryptography` are installed.
3.  **Quick Test:** Run `python3 src/test_all_configs.py` to confirm the local environment is stable.
4.  **Hardware Launch:** 
    *   Connect USRPs via SMA with **30dB attenuators**.
    *   Set roles in CLI: `python3 src/usrp_transceiver.py --role ALPHA` (Master) and `BRAVO` (Slave).
5.  **Digital Duel:** Refer to `RULES_OF_ENGAGEMENT.md` and `PARTICIPANT_HANDBOOK.md`.

### 6. File List for Review
*   `OPAL_VANGUARD_FLOW.md`: Complete signal chain logic.
*   `RANGE_SETUP_GUIDE.md`: Mandatory hardware wiring instructions.
*   `PARTICIPANT_HANDBOOK.md`: Instructions for the Blue and Red teams.
