# Opal Vanguard: Hardware Upgrade Path
## From "Desk Prototype" to "Tactical Grade" SDR Lab

This guide outlines the hardware required to move from basic software-timed FHSS to professional-grade, phase-coherent, and jam-resistant tactical datalinks.

---

### 🟢 Tier 1: The Foundation (Budget)
*Focus: Frequency Stability and RF Cleanup*
*   **High-Stability Reference (Leo Bodnar Mini GPSDO):** Provides a single 10MHz reference clock. Connecting this to the USRP's "Ref In" ensures your center frequency never drifts, even as the radios heat up. (~$120)
*   **915MHz SAW Bandpass Filters:** Small SMA blocks that plug into the RX port. They filter out LTE, WiFi, and LoRa noise, allowing your receiver to "hear" ALPHA much more clearly. (~$25/ea)
*   **SMA Torque Wrench (8 in-lb):** Ensures all connections are tightened to the exact same pressure. Crucial for repeatable results in RF testing. (~$40)

### 🟡 Tier 2: Field Ready (Professional)
*Focus: Precision Time-of-Day (TOD) and Signal Gain*
*   **Dual-Port GPSDO (Leo Bodnar Dual):** Provides both a 10MHz clock AND a 1PPS (Pulse Per Second) signal. This allows the Opal Vanguard code to hop exactly on the start of a GPS second, hitting 99.9% sync reliability. (~$180)
*   **900MHz Yagi-Uda Antennas:** High-gain directional antennas. Allows you to test "Spatial Filtering"—where you can physically point your link away from the Red Team's jammer to survive an attack. (~$60/ea)
*   **Low Noise Amplifier (Nooelec LaNA):** A high-quality wideband LNA to boost weak signals before they hit the USRP's internal mixer. (~$30)

### 🔴 Tier 3: Mission Master (Lab Grade)
*Focus: Coherence, Automation, and Advanced EW*
*   **Ettus Research OctoClock-G:** The ultimate lab tool. It takes one GPS signal and distributes identical 10MHz and 1PPS signals to up to 8 USRPs. This allows for **Phase Coherent** operations (MIMO, Beamforming). (~$1,500+)
*   **USB Programmable Step Attenuator (Mini-Circuits or similar):** Replaces your fixed 30dB blocks. You can write a Python script to "move" the radios apart digitally, testing the exact breakdown point of your Reed-Solomon FEC. (~$400)
*   **USRP B210:** An upgrade from the B205mini. It features two RX and two TX channels, allowing you to run ALPHA and a "Stealth Monitor" on the same device. (~$1,300)

---

### 🔍 Advanced Concepts to Research
Beyond hardware, look into these concepts to expand the Opal Vanguard code:

1.  **1PPS Triggering:**
    *   Instead of `time.time()`, use `usrp.set_time_next_pps()`. This aligns the internal USRP clock to the GPS clock for nanosecond-accurate hopping.
2.  **MIMO & Beamforming:**
    *   With two antennas on a B210, you can use "Null-Steering" to digitally ignore the direction the Jammer is coming from.
3.  **Burst-Mode Power Control:**
    *   Modify the `packetizer` to increase TX power only during the burst and drop to zero otherwise, making your signal even harder for an adversary to detect (LPI/LPD).
4.  **Angle of Arrival (AoA):**
    *   Using two receivers and an OctoClock, you can calculate exactly where the Red Team jammer is located based on the phase difference between antennas.

---
*Status: OPAL VANGUARD hardware logic is ready for integration with any of the above components.*
