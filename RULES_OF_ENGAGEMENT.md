# Opal Vanguard: Digital Duel (EW Competition Guide)

This document outlines the ramping difficulty levels for the team competition. The goal of the **Blue Team** is to maintain a readable "Mission Successful" log. The goal of the **Red Team** is to disrupt the link using the `top_block_gui.py` stress sliders.

---

## Level 1: The "Soft" Link
*   **Config:** `use_fec: false`, `use_dsss: false`, `use_interleaving: false`
*   **Red Team Objective:** **Denial of Service.**
    *   Use the **Noise Voltage** slider. A setting of `~0.10V` should completely kill the link.
*   **Lesson:** Basic GFSK is extremely fragile.

## Level 2: The "Repairable" Link
*   **Config:** `use_fec: true`, `use_interleaving: false`
*   **Red Team Objective:** **Burst Jamming.**
    *   Instead of steady noise, use the **Burst Jammer** at high intensity (`>50%`). 
    *   Wait for the "CRC FAILED" logs.
*   **Lesson:** FEC can fix random bits, but concentrated bursts wipe out whole blocks.

## Level 3: The "Resilient" Link
*   **Config:** `use_fec: true`, `use_interleaving: true`
*   **Red Team Objective:** **Saturation.**
    *   Bursts will now be repaired by the Interleaver/FEC combo. The Red Team must now ramp **Noise Voltage** significantly higher to find the new breaking point.
*   **Lesson:** Shuffling data (Interleaving) forces the jammer to work harder.

## Level 4: The "Stealth" Link (Current State)
*   **Config:** `use_dsss: true` (31 chips)
*   **Red Team Objective:** **Wideband Interference.**
    *   The signal is now "buried" in the noise. Red Team must push **Noise Voltage** to `0.40V+` and use **Frequency Offsets** to try and push the GFSK demodulator out of its tracking range.
*   **Lesson:** Correlation gain allows comms even when the signal-to-noise ratio is negative.

## Level 5: The "Blackout" Challenge
*   **Config:** Enable **ALL** enhancements + **AES Hopping**.
*   **Red Team Objective:** **Manipulation.**
    *   Try to find a combination of **Timing Offset**, **Freq Offset**, and **Noise** that causes the `session_manager` to drop back to `IDLE`.
*   **Lesson:** To kill an elite link, you must attack the synchronization logic, not just the raw bits.
