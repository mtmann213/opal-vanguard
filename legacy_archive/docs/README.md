# Opal Vanguard - SDR Tactical OFDM Transceiver

Opal Vanguard is a high-performance, modular software-defined radio (SDR) system designed for resilient communications in contested RF environments. It features advanced multi-carrier modulation, AES-encrypted messaging, and TOD-synchronized Frequency Hopping.

## 🚀 Current Status (v10.2)
The system is currently in the **Level 7 (OFDM Master)** phase, optimized for high-speed, multi-carrier tactical links on **USRP B205mini/B210** hardware.
- **Level 1-3**: Stable GFSK baseline with RS(15,11) FEC.
- **Level 4-5**: Stealth (DSSS) and Secure Blackout (AES + TOD-FHSS) modes functional.
- **Level 6**: Tactical Link-16 (CCSK + AFH) emulation stabilized.
- **Level 7**: High-speed **OFDM** (64 carriers, 2Msps) implemented for broadband tactical data.

## 🛠 Core Features
- **OFDM Physical Layer**: 64-carrier Orthogonal Frequency Division Multiplexing with BPSK mapping.
- **Tactical Throughput**: 2.0 Msps sample rate with 1024-byte packet frames.
- **COMSEC**: AES-CTR encryption and AES-based TOD-synchronized Frequency Hopping.
- **FEC & Hardening**: RS(15,11) error correction, matrix interleaving, and CCSK spreading.
- **Real-time Diagnostics**: Dashboard with Spectrum Waterfall, Burst Scope, and FEC health metrics.

## 🎮 Quick Start
1.  **Sync System Clocks**: Unix epoch time must match on all terminals for TOD-FHSS.
2.  **Verify Hardware**:
    ```bash
    sudo python3 src/hw_smoke_test.py --role RX --serial <SERIAL>
    ```
3.  **Launch Level 7 Radio**:
    ```bash
    export PYTHONPATH=$PYTHONPATH:$(pwd)/src
    sudo -E python3 src/usrp_transceiver.py --role ALPHA --config mission_configs/level7_ofdm_master.yaml
    ```
4.  **Monitor**: Use the **Spectrum Waterfall** to manage receiver saturation and the **Signal Scope** to verify OFDM frame capture.

## 📚 Documentation
- **[USER_MANUAL.md](USER_MANUAL.md)**: Operation guide and tactical glossary.
- **[MISSION_CONFIG_GUIDE.md](MISSION_CONFIG_GUIDE.md)**: Breakdown of OFDM and Tuning parameters.
- **[OPAL_VANGUARD_FLOW.md](OPAL_VANGUARD_FLOW.md)**: Technical history and evolution from GFSK to OFDM.
- **[GEMINI_RESUME.md](GEMINI_RESUME.md)**: Current operational handoff and mission status.
