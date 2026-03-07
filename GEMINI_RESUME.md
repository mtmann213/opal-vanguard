# Opal Vanguard - Gemini CLI Handoff (Master Build v8.1)

## 🎯 Current Status: MISSION SUCCESS
Established a stable, encrypted, frequency-hopping RF link between ALPHA and BRAVO. 
- **Baseline Logic**: Hamming-based syncword detection (2-bit error tolerance) is fully operational.
- **Hardware Integration**: Burst timing (SOB/EOB) is stabilized; no more `check_topology` crashes.
- **Level 5 Baseline**: FHSS (20 channels) + COMSEC (AES-CTR) verified over-the-air.

## 🚀 Next Step: Level 6 (Link-16)
The objective is to enable **Adaptive Frequency Hopping (AFH)** and **CCSK Spreading**.
- **Current Blockers**: None. Level 5 stability is achieved.
- **Goal**: Implement "Blacklist Syncing" where Node A informs Node B of jammed channels.

## 📋 Resume Command (ALPHA)
```bash
# 1. Sync repository
git fetch origin && git reset --hard origin/main

# 2. Launch ALPHA Radio (Level 5 Goal)
sudo -E python3 src/usrp_transceiver.py --role ALPHA --serial 3449AC1 --config mission_configs/level5_blackout.yaml
```

## 🛠 Key Tuning
- **RX Gain**: If the Waterfall is yellow, **DECREASE RX GAIN** to improve SNR.
- **Clock Sync**: Ensure system time matches on both laptops before running FHSS.
