# Opal Vanguard: Digital Duel (EW Competition Guide)

This document outlines the ramping difficulty levels for the team competition. The goal of the **Blue Team** is to maintain a readable "Mission Successful" log. The goal of the **Red Team** is to disrupt the link using the `top_block_gui.py` stress sliders.

---

## Level 1: The "Soft" Link
*   **Config:** `mission_configs/level1_soft_link.yaml`
*   **Red Team Objective:** **Denial of Service.**
    *   Use the `adversary_jammer.py` script in `NOISE` mode. A moderate gain setting should completely kill the link.
*   **Lesson:** Basic GFSK is extremely fragile.

## Level 2: The "Repairable" Link
*   **Config:** `mission_configs/level2_repairable.yaml`
*   **Red Team Objective:** **Burst Jamming.**
    *   Instead of steady noise, use the `adversary_jammer.py` in `PULSE` mode or `SWEEP` mode. 
    *   Wait for the "CRC FAILED" logs.
*   **Lesson:** FEC can fix random bits, but concentrated bursts wipe out whole blocks.

## Level 3: The "Resilient" Link
*   **Config:** `mission_configs/level3_resilient.yaml`
*   **Red Team Objective:** **Saturation.**
    *   Bursts will now be repaired by the Interleaver/FEC combo. The Red Team must now ramp **Gain** significantly higher to find the new breaking point.
*   **Lesson:** Shuffling data (Interleaving) forces the jammer to work harder.

## Level 4: The "Stealth" Link (Current State)
*   **Config:** `mission_configs/level4_stealth.yaml`
*   **Red Team Objective:** **Wideband Interference.**
    *   The signal is now "buried" in the noise. Red Team must push **Gain** high and try `SWEEP` to push the GFSK demodulator out of its tracking range.
*   **Lesson:** Correlation gain allows comms even when the signal-to-noise ratio is negative.

## Level 5: The "Blackout" Challenge
*   **Config:** `mission_configs/level5_blackout.yaml`
*   **Red Team Objective:** **Manipulation.**
    *   Try to find a combination of attacks that causes the `session_manager` to drop back to `IDLE`.
*   **Lesson:** To kill an elite link, you must attack the synchronization logic, not just the raw bits.

## Level 6: The "Link 16" Challenge
*   **Config:** `mission_configs/level6_link16.yaml`
*   **Hardening:** 500ms TOD-Synced Hopping, RS(31,15) FEC, **32-chip CCSK symbol mapping**, GFSK Modulation.
*   **Red Team Objective:** **Total Denial.**
    *   With hardened RS(31,15) FEC and CCSK spreading, the signal is extremely resilient. Red Team must use high-power wideband noise to disrupt the link.
*   **Lesson:** Professional tactical links combine multiple layers of time, frequency, and code-space protection to ensure survival.

## Level 7: The "OFDM Master" Challenge
*   **Config:** `mission_configs/level7_ofdm_master.yaml`
*   **Hardening:** Wideband OFDM modulation with 64 subcarriers, fast AFH, and 1PPS nanosecond-accurate hardware triggering.
*   **Red Team Objective:** **Surgical Strike.**
    *   OFDM spreads data across many subcarriers. Red Team must attempt to surgically jam specific sub-bands or overpower the entire 2MHz channel.
*   **Lesson:** Orthogonal frequency division provides massive throughput while natively resisting narrowband interference.
