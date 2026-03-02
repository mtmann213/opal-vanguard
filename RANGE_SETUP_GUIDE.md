# Opal Vanguard: Range Setup Guide
## Technical Instructions for the Range Master

This guide details the physical and software configuration required to host the "Digital Duel" EW competition.

---

## 1. Physical Architecture (The "Arena")
To prevent hardware damage and ensure repeatable results, all testing should be conducted over SMA coaxial cables.

### Hardware Required:
*   3x USRP B210 or B205mini (2 for Blue Team, 1 for Red Team).
*   3x SMA-to-SMA Coaxial Cables.
*   3x 20dB or 30dB Fixed Attenuators (Mandatory).
*   1x 3-Port SMA Power Splitter/Combiner.
*   3x Linux PCs with UHD and GNU Radio 3.10 installed.

### Wiring Diagram:
```text
[BLUE ALPHA PC] --(USB 3.0)-- [USRP A]
                                 |
                          [30dB Attenuator]
                                 |
                          [COMBINER PORT 1]
                                 |
[RED TEAM PC]   --(USB 3.0)-- [USRP R] -- [30dB Attenuator] -- [COMBINER PORT 2]
                                 |
                          [COMBINER PORT 3]
                                 |
                          [30dB Attenuator]
                                 |
[BLUE BRAVO PC] --(USB 3.0)-- [USRP B]
```

---

## 2. Software Deployment

### Prerequisites:
1.  Ensure all three PCs have the latest code from the `hardware/usrp-integration` branch.
2.  Install Python dependencies: `pip install pyyaml cryptography numpy`.

### Launch Sequence:

**Step 1: Blue Alpha (Master)**
```bash
sudo -E python3 src/usrp_transceiver.py --role ALPHA --serial <SERIAL_A> --config mission_configs/level1_soft_link.yaml
```

**Step 2: Blue Bravo (Slave)**
```bash
sudo -E python3 src/usrp_transceiver.py --role BRAVO --serial <SERIAL_B> --config mission_configs/level1_soft_link.yaml
```

**Step 3: Verification**
Observe the console output on both Blue PCs. The status should report `[DATA RX]` and "Mission Data" should begin to appear.

---

## 3. Red Team Setup (The Jammer)
The Red Team uses the dedicated jammer script to generate precise interference against the Blue Team.

### Launching the Jammer:
```bash
sudo -E python3 src/adversary_jammer.py --serial <SERIAL_R> --mode NOISE --gain 75
```
Options for mode include `NOISE`, `SWEEP`, and `PULSE`.

---

## 4. Range Master Responsibilities:
*   **Monitor Safety:** Ensure attenuators are securely attached before any software is started.
*   **Arbitrate Sync:** If the Blue Team uses `sync_mode: TOD`, ensure all PC system clocks are synchronized to within 1ms using NTP or a shared local reference.
*   **Reset the Range:** Between competition levels, use the "Clear Mission Log" button to reset the score.
