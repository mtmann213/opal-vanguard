# Opal Vanguard - SDR Tactical Transceiver

Opal Vanguard is a high-performance, modular software-defined radio system designed for resilient communications in contested RF environments. It supports advanced features such as AES-encrypted messaging, Frequency Hopping (FHSS), and Direct Sequence Spread Spectrum (DSSS).

## 🚀 Current Status (v8.1)
The system has been fully stabilized for the **B205mini** hardware and **N150-class CPUs**. 
- **Levels 1-3**: Rock-solid baseline connectivity with RS(15,11) FEC and ARQ retries.
- **Level 4**: Stealth mode functional with DSSS spreading and Ghost Mode (LPI).
- **Level 5**: Secure Blackout mode functional with AES-CTR encryption and TOD-synchronized FHSS.

## 🛠 Core Features
- **Robust Sync**: Hamming-distance based syncword detection allowing up to 2-bit errors.
- **COMSEC**: AES-CTR encryption for error-resilient secure payloads.
- **Burst Stability**: Custom `BurstTagger` logic ensuring perfect USRP T/R switch timing.
- **Real-time Diagnostics**: GUI-integrated Spectrum Waterfall and Burst Scope.

## 🎮 Quick Start
1.  **Synchronize Clocks**: Ensure system time matches on both terminals (crucial for FHSS).
2.  **Launch Radio**:
    ```bash
    sudo -E python3 src/usrp_transceiver.py --role ALPHA --serial <SERIAL> --config mission_configs/level5_blackout.yaml
    ```
3.  **Monitor**: Use the **Signal Scope** to verify bit-level recovery and the **Waterfall** to manage receiver saturation.

## 📚 Documentation
- **[USER_MANUAL.md](USER_MANUAL.md)**: Operation guide and technical glossary.
- **[MISSION_CONFIG_GUIDE.md](MISSION_CONFIG_GUIDE.md)**: Detailed breakdown of tuning parameters.
- **[GEMINI_RESUME.md](GEMINI_RESUME.md)**: Operational handoff and current objectives.
