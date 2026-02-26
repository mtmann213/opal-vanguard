# Mission Hand-off: Project Opal Vanguard (EW READY)
## Session State: Tuesday, February 24, 2026

### 1. Project Status: Contested Environment Ready
Opal Vanguard has transitioned into a highly sophisticated "Electronic Warfare Range." The signal chain now features military-grade hardening including DSSS, NRZ-I, Manchester Encoding, and AES-CTR hopping.

### 2. Technical Achievement Summary
*   **PHY/Link:** 31-chip DSSS (M-sequence), GFSK modulation index calibrated to 1.0, NRZ-I phase resilience, and 8-row Matrix Interleaving.
*   **Hopping:** Fully functional **AES-CTR** sequence generator. 
*   **Synchronization:** Implemented **Time-of-Day (TOD) Sync** for stealthy, handshake-free communication.
*   **Config:** Unified `config.yaml` with exhaustive documentation for EW training.
*   **Hardware:** Full scaffolding for **USRP B210 / B205mini** with real-time health dashboard.

### 3. Primary Command Center
*   **`src/usrp_transceiver.py`**: Field-ready hardware terminal with CLI role selection (`--role ALPHA/BRAVO`).
*   **`src/top_block_gui.py`**: Software simulation lab with wideband 10MHz visualization and stress-test sliders.
*   **`config.yaml`**: The "Mission Manual" for all signal toggles.

### 4. Verification Benchmarks
*   **Simulation Stress:** Link survives ~0.40V AWGN and 100% burst jammer with DSSS and Interleaving enabled.
*   **Digital Integrity:** `python3 src/test_loopback.py` verifies the entire 10-step chain passes CRC.
*   **Diagnostics:** Terminal now outputs real-time CRC results, bit inversion status, and FEC repair counts.

### 5. Immediate Next Steps
1.  **Hardware Range Test:** Deploy to 2 separate computers with USRPs and SMA attenuators as per `RANGE_SETUP_GUIDE.md`.
2.  **Digital Duel Round 1:** Start at Level 1 (Soft Link) and have the Red Team jam the signal, then ramp up Blue Team hardening via `config.yaml`.
3.  **Fast Hopping Optimization:** Experiment with reducing `dwell_time_ms` to <20ms using the TOD-Sync mode.

### 6. Resumption Instructions
1.  Verify branch: `git checkout hardware/usrp-integration`.
2.  Run `python3 src/top_block_gui.py` to confirm the simulation logic.
3.  Observe terminal for the restored diagnostic logs.
