# Opal Vanguard - Gemini CLI Handoff (Master Build v7.6)

## 🎯 Current Objective
Establish a rock-solid P2P RF link between Laptop 1 (BRAVO) and Laptop 2 (ALPHA) using USRP B205mini hardware. Current focus is **Level 3: Resilient** baseline testing.

## 🛠️ State of the Build (v7.6)
We have stripped the codebase down to an **Absolute Stability Baseline** to eliminate SegFaults and PMT errors.

### 🏁 Critical Fixes Implemented:
1.  **Bit-Packing Restoration:** `packetizer.py` now outputs **unpacked bits** (1 bit per byte). This is mandatory for GNU Radio modulators to send a valid signal.
2.  **AMC Auto-Reboot Disabled:** Automatic mission switching is physically stripped from `usrp_transceiver.py` to prevent Segmentation Faults during USRP hardware release.
3.  **AFH Blacklist Logic Stubbed:** `handle_blacklist` in hop generators is a no-op stub to prevent `AttributeError: is_vector_obj` crashes in GNU Radio 3.10.
4.  **Header Alignment:** `interleaver_rows` is set to **8** for Levels 1-5 (120-byte blocks) and **32** for Level 6 (320-byte blocks).
5.  **Virtual Wipe:** Dashboard UI now uses browser-side timestamp filtering for telemetry wipes, bypassing `sudo` file permission issues.

## 🚀 Laptop 2 Setup (ALPHA)
The next agent should perform the following to resume:

```bash
# 1. Force hard sync to main
git fetch origin
git reset --hard origin/main

# 2. Purge Python cache
find . -name "__pycache__" -type d -exec rm -rf {} +

# 3. Launch ALPHA Radio
sudo -E python3 src/usrp_transceiver.py --role ALPHA --serial 3457480 --config mission_configs/level3_resilient.yaml
```

## 📋 Mission Log
- **Level 1 & 2:** Stable.
- **Level 3:** Freezing fixed. Payloads restored.
- **Next Step:** Verify "HEARTBEAT FROM ALPHA" is received correctly by BRAVO on Laptop 1.
