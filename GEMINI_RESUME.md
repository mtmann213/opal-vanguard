# Mission Hand-off: Project Opal Vanguard (TACTICAL BUILD v3.0)
## Session State: Thursday, March 5, 2026

### 1. Project Status: Deployment Ready & Hardened
The system has evolved from a basic FHSS simulator into a professional-grade Electronic Warfare (EW) testbed. All core modules are verified on physical USRP hardware.

**Current Branch:** `main` (fully synced with `hardware/usrp-integration`)

### 2. Full Capability Stack
*   **Modulations:** GFSK, MSK, DBPSK, DQPSK, D8PSK, and wideband OFDM.
*   **Applications:**
    *   `chat`: Real-time tactical messaging via PyQt UI.
    *   `file`: Chunked FTP with ARQ reassembly for image/data transfer.
    *   `heartbeat`: Automated signal presence pulses.
*   **Security:**
    *   **COMSEC:** AES-256-GCM authenticated payload encryption.
    *   **TRANSEC:** TOD-synced and AES-CTR frequency hopping.
*   **Resilience:**
    *   **MAC:** Automatic Repeat Request (ARQ) and Adaptive Frequency Hopping (AFH) channel blacklisting.
    *   **PHY:** Reed-Solomon (15,11) and (31,15) FEC; DSSS (31-chip) and CCSK (32-chip) spreading.
    *   **LPI/LPD:** "Ghost Mode" hardware power control (TX Gain 0 between bursts).

### 3. Analytics & Visualization
*   **Telemetry:** Structured JSONL logging (`mission_telemetry.jsonl` and `jammer_telemetry.jsonl`).
*   **Commander Dashboard:** Flask-based web UI (`http://localhost:5000`) with live Chart.js visualization of signal confidence, success rates, and Jammer strikes.

### 4. Resumption Instructions (New Machine)
1.  **Clone & Bootstrap:**
    ```bash
    git clone <repo_url>
    cd opal-vanguard
    chmod +x SETUP_MISSION.sh
    ./SETUP_MISSION.sh
    ```
2.  **Verify Digital Logic:**
    ```bash
    python3 src/test_all_configs.py
    ```
3.  **Launch Hardware Link (Example: Level 4 Stealth):**
    *   **PC 1:** `sudo -E python3 src/usrp_transceiver.py --role ALPHA --serial <S1> --config mission_configs/level4_stealth.yaml`
    *   **PC 2:** `sudo -E python3 src/usrp_transceiver.py --role BRAVO --serial <S2> --config mission_configs/level4_stealth.yaml`
4.  **Launch Dashboard:**
    ```bash
    python3 dashboard/app.py
    ```

### 5. Next Objectives
*   **Follower Jammer Testing:** Use `src/adversary_jammer.py --mode FOLLOWER --log-telemetry` to pressure the link.
*   **OFDM Optimization:** Fine-tune Level 7 OFDM subcarriers for higher throughput.
*   **GPSDO Integration:** Once hardware arrives, switch `sync: pc_clock` to `sync: external` in YAML configs for nanosecond-accurate 1PPS hopping.
