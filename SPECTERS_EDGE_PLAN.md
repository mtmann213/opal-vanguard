# Mission Plan: Specter's Edge (Operational Robustness)
**Objective:** Capture 250,000+ snapshots of "Dirty" real-world data to transition the model from a lab-environment specialist to a field-ready Neural Receiver.

## 1. Phase 4: Environmental & Operational Diversity
The "Industrial" dataset taught the model the hardware's accent. This phase teaches the model the "chaos of the world."

### A. Spatial Diversity (The "Multipath" Sweep)
Instead of a fixed setup, we vary the physical environment:
*   **LOS (Line of Sight):** Antennas visible to each other.
*   **NLOS (Non-Line of Sight):** Place USRP #2 (Receiver) in another room or behind a metallic object.
*   **Low-Level Multipath:** Place antennas near reflective surfaces (windows, cabinets) to create intentional echoes.

### B. Dynamic Range (The "Gain" Waterfall)
The model needs to identify signals at the edge of sensitivity:
*   **Step Sweep:** Record every modulation at TX Gains from 10dB (barely audible) to 70dB (near saturation) in 5dB steps.
*   **Purpose:** Builds a model that can identify "whispers" in the noise as well as "shouts."

### C. Electronic Warfare (The "Jamming Gauntlet")
Using USRP #3 (Adversary) for advanced interference:
*   **Continuous Wave (CW) Jamming:** A simple tone on top of the signal.
*   **Swept Jamming:** A noise burst that moves across the signal's bandwidth.
*   **Intermittent Jamming:** Short, random "stutter" bursts to teach the AI to reconstruct signals from fragments.

## 2. Dataset Collision Strategy (New Requirement)
To handle the "Multiple signals on top of each other" problem we discussed:
*   **Co-Channel Interference:** USRP #1 sends BPSK, USRP #3 sends a *different* BPSK signal on the exact same frequency.
*   **Adjacent Channel Interference:** USRP #3 sends high-power FM 200kHz away from the target center.

## 3. Technical Implementation on Dell Laptop

### Task 1: The "Specter Sequencer" (`src/specter_sequencer.py`)
Upgrade the current sequencer to handle **Nested Loops** for:
1.  Environment Type [Lab, NLOS, Multipath]
2.  TX Gain [10, 20, 30, 40, 50, 60, 70]
3.  Modulation [The 24 Class List]
4.  Jamming State [None, CW, Swept, Intermittent]

### Task 2: Metadata Deep-Linking
Every snapshot in the `Z` matrix must now record:
*   `Environment_ID` (Integer mapping to the physical room setup)
*   `Measured_RSSI` (Actual received signal strength)
*   `Jammer_Type_ID` (0=None, 1=CW, 2=Swept, 3=Intermittent)

## 4. The Laptop "Flight Checklist"
1.  **Antenna Check:** Use the 3dB high-gain antennas for the NLOS tests.
2.  **Thermal Monitoring:** Run the 5-minute warm-up before every 50,000 samples.
3.  **HDF5 Incremental:** The laptop should write to `VDF_SPECTER_ALPHA.h5` incrementally to survive the system freezes we saw earlier.

---
**Status:** Ready for Branch `sidequest/specters-edge` on the Dell Laptop.
