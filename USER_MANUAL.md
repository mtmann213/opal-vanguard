# Opal Vanguard: Comprehensive User Manual

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Introduction](#1-introduction)
3. [Concept of Employment (CONEMP)](#2-concept-of-employment-conemp)
4. [Concept of Operations (CONOPS)](#3-concept-of-operations-conops)
5. [System Architecture & Capabilities](#4-system-architecture--capabilities)
6. [Mission Tiers (The "Digital Duel")](#5-mission-tiers-the-digital-duel)
7. [Operator's Guide](#6-operators-guide)
8. [Glossary & Acronyms](#7-glossary--acronyms)

---

## Executive Summary
**Project Opal Vanguard** is a highly scalable, Software-Defined Radio (SDR) testbed designed specifically for Electronic Warfare (EW) training and tactical datalink research. Developed utilizing Python and GNU Radio, it provides a physical, hardware-in-the-loop environment to simulate, analyze, and defeat electromagnetic interference and jamming.

**The Value Proposition:**
Modern tactical communications rely on complex layers of protection—frequency hopping, mathematical error correction, and cryptographic spreading—to survive in contested airspace. Historically, training personnel on these systems required multi-million-dollar military hardware. Opal Vanguard democratizes this capability. 

By leveraging Commercial Off-The-Shelf (COTS) hardware (such as the USRP B205mini), Opal Vanguard allows engineering teams, researchers, and operators to:
*   **Train** in live "Red vs. Blue" electronic combat scenarios.
*   **Develop** and evaluate novel anti-jamming algorithms (e.g., Adaptive Frequency Hopping) safely in a laboratory.
*   **Visualize** the mathematical theories behind advanced datalinks (like the military's Link-16) in real-time.

For leadership, Opal Vanguard represents a low-cost, high-yield asset that rapidly accelerates organizational EW readiness and RF (Radio Frequency) engineering proficiency.

---

## 1. Introduction
Welcome to Opal Vanguard. This manual serves as the definitive guide for operating, deploying, and understanding the platform. The system implements a complete digital communication chain, starting from basic, vulnerable transmissions and scaling up to nanosecond-synchronized, adaptive hopping networks.

Whether you are an operator attempting to punch a signal through a wall of broadband noise, or an adversary attempting to systematically dismantle a communications link, this platform provides the tools required.

---

## 2. Concept of Employment (CONEMP)
**How is Opal Vanguard used by the organization?**

Opal Vanguard is deployed primarily in three modalities:

1.  **The Training Range:** Used to train personnel in the realities of RF physics. By progressing through the "Mission Tiers," trainees learn how individual layers of signal hardening (like Interleaving or Forward Error Correction) respond to different types of jamming.
2.  **The R&D Testbed:** Used by engineers to prototype new datalink features. Because the system is written in modular Python, engineers can quickly inject new modulation schemes (like OFDM) or MAC (Medium Access Control) logic without rewriting low-level FPGA code.
3.  **Hardware Evaluation:** Used to test the limits of COTS SDR hardware, evaluating clock drift, tuning latency, and RF front-end performance in dense signal environments.

---

## 3. Concept of Operations (CONOPS)
**How does the system operate in a live scenario?**

Opal Vanguard operates on a **"Digital Duel"** framework, dividing participants into two asymmetrical roles operating in the 900MHz Industrial, Scientific, and Medical (ISM) band.

### The Blue Team (Communications)
*   **Nodes:** Operates the **ALPHA** (Transmitter) and **BRAVO** (Receiver) terminals.
*   **Objective:** Maintain a continuous, error-free flow of "Mission Data" from Alpha to Bravo.
*   **Capabilities:** Blue Team utilizes the `mission_configs/` files to dynamically alter the structure of their radio waves. They can change modulations, add spreading codes, or enable autonomous evasion tactics.

### The Red Team (Adversary)
*   **Nodes:** Operates the **JAMMER** terminal (`adversary_jammer.py`).
*   **Objective:** Disrupt, Deny, Degrade, or Manipulate the Blue Team's datalink.
*   **Capabilities:** Red Team does not decode the data; their goal is destruction. They utilize broadband noise (Denial of Service), swept-frequency tones (Scanning attacks), and pulsed bursts to attack vulnerabilities in the Blue Team's current configuration.

---

## 4. System Architecture & Capabilities
Opal Vanguard's resilience is built on a "defense-in-depth" architecture. 

*   **Modulation Suite:** Converts digital bits into analog waves. Supports GFSK (Gaussian Frequency Shift Keying), MSK (Minimum Shift Keying), Phase Shift Keying (DBPSK, DQPSK, D8PSK), and wideband OFDM (Orthogonal Frequency Division Multiplexing).
*   **Spreading (Stealth):** Uses DSSS (Direct Sequence Spread Spectrum) and CCSK (Cyclic Code Shift Keying) to expand the signal's bandwidth, lowering its power density to hide it below the noise floor (LPI/LPD).
*   **Forward Error Correction (FEC):** Uses mathematical algorithms, specifically Reed-Solomon (RS 15,11 and RS 31,15), to reconstruct corrupted data without needing a retransmission.
*   **Frequency Hopping Spread Spectrum (FHSS):** Changes the carrier frequency rapidly (up to 100 times per second) using cryptographic AES-CTR sequences synchronized via precise Time-of-Day (TOD) clocks.
*   **Adaptive MAC Layer:** Features ARQ (Automatic Repeat Request) for automated retransmissions, and AFH (Adaptive Frequency Hopping) which autonomously detects jammed channels and "blacklists" them, dynamically altering the hop sequence to evade the Red Team.

---

## 5. Mission Tiers (The "Digital Duel")
The system includes predefined configurations that incrementally introduce these capabilities.

*   **Level 1: Soft Link** - Raw GFSK. Extremely fragile; easily destroyed by low-power noise.
*   **Level 2: Repairable** - Adds basic FEC. Survives random bit flips but fails against sustained bursts.
*   **Level 3: Resilient** - Adds Matrix Interleaving and ARQ. Bursts of noise are spread out and repaired.
*   **Level 4: Stealth** - Adds DSSS. The signal is buried in noise, forcing the Jammer to use massive power.
*   **Level 5: Blackout** - Adds AES Frequency Hopping and AFH. The link rapidly evades narrowband attacks and blacklists jammed channels.
*   **Level 6: Link-16** - Emulates military tactical datalinks. Uses MSK, CCSK 32-chip mapping, and aggressive RS(31,15) correction.
*   **Level 7: OFDM Master** - Replaces single-carrier modulation with 64-subcarrier OFDM and nanosecond-accurate hardware clock triggering.

---

## 6. Operator's Guide
### Physical Setup
1. Deploy three Linux PCs, each connected to one USRP (Universal Software Radio Peripheral) via USB 3.0.
2. Connect the RF ports using SMA cables and **at least 60dB of attenuation** to prevent hardware damage. 
3. Use an RF Combiner/Splitter to merge the signals:
   * **Node 1 (Blue Alpha):** Connects to Port 1 of the combiner.
   * **Node 3 (Red Jammer):** Connects to Port 2 of the combiner.
   * **Node 2 (Blue Bravo):** Connects to the combined Port 3.
   * *This ensures the receiver (Bravo) sees both the legitimate signal and the jamming interference simultaneously.*

### Environment Bootstrap
Run the setup script to install all dependencies and verify the digital logic:
```bash
./SETUP_MISSION.sh
```
*(Alternatively, deploy using the `DOCKER_GUIDE.md` instructions for an isolated environment).*

### Executing a Mission
The mission requires three separate command instances, typically run on their respective hardware-connected PCs.

**Computer 1 (Blue Alpha):**
```bash
sudo -E python3 src/usrp_transceiver.py --role ALPHA --serial <SERIAL_A> --config mission_configs/level4_stealth.yaml
```

**Computer 2 (Blue Bravo):**
```bash
sudo -E python3 src/usrp_transceiver.py --role BRAVO --serial <SERIAL_B> --config mission_configs/level4_stealth.yaml
```

**Computer 3 (Red Jammer):**
```bash
sudo -E python3 src/adversary_jammer.py --serial <SERIAL_J> --mode SWEEP --gain 75
```

---

## 7. Glossary & Acronyms
*   **1PPS (One Pulse Per Second):** An electrical signal, usually from a GPS receiver, that precisely marks the start of a second. Used for nanosecond hardware synchronization.
*   **AFH (Adaptive Frequency Hopping):** A system that monitors spectrum health and autonomously avoids channels experiencing heavy interference.
*   **ARQ (Automatic Repeat Request):** A protocol where the receiver automatically asks the transmitter to resend a specific packet if it was corrupted.
*   **CCSK (Cyclic Code Shift Keying):** A modulation technique where different data symbols are represented by cyclically shifting a base sequence of chips. Used in Link-16.
*   **COTS (Commercial Off-The-Shelf):** Standard hardware available to the public, as opposed to custom-built military hardware.
*   **CRC (Cyclic Redundancy Check):** A checksum attached to a packet to detect accidental changes to raw data.
*   **DSSS (Direct Sequence Spread Spectrum):** A transmission method that multiplies data bits by a high-speed "chipping code" to spread the signal over a wider bandwidth.
*   **EW (Electronic Warfare):** Any action involving the use of the electromagnetic spectrum to attack an enemy or impede enemy assaults.
*   **FEC (Forward Error Correction):** A method of adding redundant data to a transmission so the receiver can mathematically correct errors without asking for a retransmission.
*   **FHSS (Frequency Hopping Spread Spectrum):** A method of transmitting radio signals by rapidly changing the carrier frequency among many distinct frequencies.
*   **GFSK / MSK / PSK:** Types of digital modulation (Frequency, Minimum, and Phase Shift Keying) that define exactly how 1s and 0s are encoded into analog waves.
*   **GPSDO (GPS Disciplined Oscillator):** Hardware that uses GPS satellite timing to generate an incredibly precise and stable clock reference for a radio.
*   **LPI / LPD (Low Probability of Intercept / Detection):** Techniques used to make a signal difficult for an adversary to find or decode.
*   **OFDM (Orthogonal Frequency Division Multiplexing):** A method of encoding digital data on multiple carrier frequencies simultaneously (subcarriers).
*   **SDR (Software-Defined Radio):** A radio communication system where components that have been traditionally implemented in hardware (e.g. mixers, filters, modulators) are instead implemented by software on a computer.
*   **TOD (Time of Day):** Using an absolute clock (like Unix Epoch time) to synchronize events across separate machines without requiring them to communicate directly.
*   **USRP (Universal Software Radio Peripheral):** The specific brand of SDR hardware manufactured by Ettus Research used in this project.
