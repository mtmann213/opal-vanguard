# Opal Vanguard: Range Setup Guide
## Technical Instructions for the Range Master

This guide details the physical and software configuration required to host the "Digital Duel" EW competition.

---

## 1. Physical Architecture (The "Arena")
The project supports two primary deployment models: **Bench Verification** and **Exercise Employment**.

### Model A: Bench Verification (Single-Host)
*   **Purpose:** Initial setup, debugging, and code verification.
*   **Setup:** All 3 USRPs are connected to a single high-performance Linux PC.
*   **Execution:** Run 3 separate terminal windows. This confirms the logic and RF path are sound before distributing the hardware.

### Model B: Exercise Employment (Multi-Host)
*   **Purpose:** Live "Digital Duel" training and tactical simulation.
*   **Setup:** Three separate PCs, each with its own USRP and local instance of the repository.
*   **Execution:** Nodes are physically separated, requiring teams to coordinate timing and strategy over the RF link.

---

## 2. RF Configuration & Sniffing
To ensure the **Red Team (Jammer)** can behave reactively, the wiring must allow the Jammer to "see" the exchanges between Alpha and Bravo.

### Wiring Diagram (The "Star" Config):
```text
[BLUE ALPHA TX] ---- [30dB Attenuator] ---- [SPLITTER PORT 1]
                                                   |
[RED JAMMER TRX] --- [30dB Attenuator] ---- [SPLITTER PORT 2] (Sniffer/Injector)
                                                   |
[BLUE BRAVO RX] ---- [30dB Attenuator] ---- [SPLITTER PORT 3]
```

### Technical Note on Reactive Jamming:
*   **Sniffing:** In this configuration, the signal from Alpha (Port 1) is coupled to Port 2. Even with standard splitter isolation (typically 20-30dB), the Jammer USRP will "hear" Alpha's transmission.
*   **Reaction:** The Red Team can use this "sniffed" signal to trigger a **Reactive Jam**. By detecting the preamble of an Alpha packet, the Jammer can immediately switch to Transmit mode and inject interference before the packet finishes. 
*   **Validation:** This setup perfectly replicates a "Follow-On" jammer scenario where the adversary is geographically positioned to intercept the transmitter's sidelobes.

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
Options for mode include `NOISE`, `SWEEP`, `PULSE`, and `FOLLOWER`.

---

## 4. Range Master Responsibilities:
*   **Monitor Safety:** Ensure attenuators are securely attached before any software is started.
*   **Arbitrate Sync:** If the Blue Team uses `sync_mode: TOD`, ensure all PC system clocks are synchronized to within 1ms using NTP or a shared local reference.
*   **Reset the Range:** Between competition levels, use the "Clear Mission Log" button to reset the score.
