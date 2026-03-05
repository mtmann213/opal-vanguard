# Opal Vanguard: Participant Handbook
## The "Digital Duel" Mission Profile

### 1. Introduction
Welcome to Project Opal Vanguard. You are tasked with operating or disrupting a military-grade tactical datalink. The system utilizes Frequency Hopping Spread Spectrum (FHSS), Direct Sequence Spread Spectrum (DSSS), and Reed-Solomon Forward Error Correction (FEC) to survive in contested electromagnetic environments.

### 2. The Teams

#### **Blue Team (The Operators)**
*   **Objective:** Maintain a reliable data link between Alpha and Bravo nodes.
*   **Success Metric:** Continuous throughput of "Mission Data" with zero CRC failures.
*   **Your Tools:** You control the configuration files in `mission_configs/`. You can launch different levels (e.g., `level4_stealth.yaml`) to toggle FEC, Interleaving, DSSS, and Hopping strategies to harden your signal.

#### **Red Team (The Disruptors)**
*   **Objective:** Disrupt, Deny, Degrade, or Manipulate the Blue Team's communications.
*   **Success Metric:** Forcing the Blue Team terminal into an `IDLE` state or causing sustained "CRC FAIL" errors.
*   **Your Tools:** You have a dedicated USRP and the `src/adversary_jammer.py` script. You may use broadband noise, swept-frequency tones, or pulsed jammers.

---

### 3. Rules of Engagement
1.  **No Physical Tampering:** Do not touch the SMA cables, attenuators, or the other team's hardware.
2.  **Config Lock:** Blue Team may only change configurations *between* rounds, not while a round is active.
3.  **Frequency Discipline:** All activity must remain within the agreed-upon 900MHz ISM band.

---

### 4. Tactical Tips

#### **For Blue Team:**
*   **Stealth:** Use **DSSS** or **CCSK**. DSSS spreads your energy across the band, while CCSK provides the high-correlation symbol mapping used in military tactical links.
*   **Repair:** If you see "FEC Repairs" increasing on your dashboard, your link is under attack but surviving. Link-16 mode (Level 6) uses **RS(31,15)** which can survive losing nearly 50% of the packet symbols.
*   **Modulation:** MSK (Minimum Shift Keying) provides better spectral efficiency and a smoother phase transition than GFSK, making it harder to detect at the band edges.
*   **Phase Resilience:** If the Red Team uses frequency offsets, ensure **NRZ-I** is enabled to protect against bit-flips.

#### **For Red Team:**
*   **The Sync Attack:** Don't just jam the data. Try to jam the **Syncword**. If Blue can't find the start of the packet, the FEC and DSSS are useless.
*   **Broadband vs. Narrowband:** A strong narrowband tone is easier to avoid via hopping. A wideband noise floor is harder to hide from but requires more power from your USRP.
*   **The Handshake Snipe:** If Blue is in `HANDSHAKE` mode, a well-timed burst can prevent them from ever connecting.

---

### 5. Round Progression
*   **Round 1:** Clear channel. Get the link established.
*   **Round 2:** Red Team introduces light AWGN (Noise).
*   **Round 3:** Red Team introduces "Burst" jamming.
*   **Round 4:** Full Spectrum Contest. Anything goes.
