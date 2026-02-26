# Mission Hand-off: Project Opal Vanguard (FINAL)
## Session State: Tuesday, February 24, 2026

### 1. Project Overview
Project Opal Vanguard is a high-fidelity, military-grade FHSS messaging system designed for the USRP B210/B205mini platform. It features multi-layered signal protection and a unified configuration system for Electronic Warfare (EW) training.

### 2. Technical Stack
*   **Physical Layer:** GFSK (h=1.0, BT=0.35), DSSS (31-chip M-sequence), Manchester Encoding, NRZ-I (Phase resilience).
*   **Link Layer:** Reed-Solomon (15,11) FEC, Matrix Interleaving (8-row), CRC16/32, Whitening ($x^7+x^4+1$).
*   **Hopping:** AES-CTR Counter-based sequence, 200ms Dwell (Configurable down to <10ms).
*   **Sync:** Dual Mode - Asynchronous Handshake (SYN/ACK) or Precision Time-of-Day (TOD) Sync.

### 3. Current Working State
*   **Active Branch:** `hardware/usrp-integration`
*   **Hardware Status:** Scaffolding complete for USRP B210/B205mini.
*   **Lab Status:** 10MHz software simulation fully verified with 31-chip DSSS.

### 4. Primary Entry Points
*   **`src/usrp_transceiver.py`**: The main hardware script. Supports `--role ALPHA/BRAVO` and `--serial <ID>`.
*   **`config.yaml`**: The "Mission Manual." Every DSP and Hardware toggle is centrally controlled and documented here.
*   **`src/top_block_gui.py`**: The wideband software simulation lab with real-time stress sliders.

### 5. Essential Documentation
*   `OPAL_VANGUARD_FLOW.md`: Detailed DSP/RF signal chain architecture.
*   `RANGE_SETUP_GUIDE.md`: Wiring diagrams and attenuator requirements for USRP tests.
*   `PARTICIPANT_HANDBOOK.md`: Rules and tactical tips for the "Digital Duel" team competition.
*   `RULES_OF_ENGAGEMENT.md`: Ramping difficulty levels for EW stress testing.

### 6. Resumption Steps for Gemini CLI
1.  **Environment:** Ensure `gr-uhd` and `cryptography` are installed.
2.  **Verify Digital Chain:** Run `python3 src/test_loopback.py`. It should pass with the current `config.yaml`.
3.  **Hardware Launch:** 
    *   Connect USRPs via SMA cables with **30dB attenuators**.
    *   Run `python3 src/usrp_transceiver.py --role ALPHA` on the master PC.
4.  **EW Range:** Use the sliders in `src/top_block_gui.py` to demonstrate the link's "Breaking Point" to the team.
