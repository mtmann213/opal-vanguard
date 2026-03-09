# Opal Vanguard: System Architecture & Developer Guide

## 📡 1. Executive Summary
Opal Vanguard is a **Tactical Data Link (TDL)** system designed for resilient, secure communications using Software Defined Radio (SDR). For a software developer, it is best understood as a **Packet-Switched Network** running over a volatile, half-duplex physical medium.

The system is entirely **Config-Driven**. A single YAML file defines the Physical (PHY), MAC, and Link layer parameters, allowing the radio to transform from a simple 915MHz GFSK link to a complex, frequency-hopping OFDM broadband pipe without changing a single line of code.

---

## 🛤️ 2. The Life of a Packet (Data Flow)

To evaluate the code, follow the data as it moves through these three primary domains:

### A. The Application Domain (`usrp_transceiver.py`)
1. User types a message in the Qt GUI.
2. The UI emits a signal containing a string.
3. This is wrapped into a **PDU (Protocol Data Unit)**—a PMT dictionary + data vector—and sent to the **Session Manager**.

### B. The Link Layer Domain (`packetizer.py`)
1. **Encryption**: Application data is encrypted using AES-256 CTR.
2. **Framing**: A 4-byte header (SrcID, Type, Seq, Length) is attached.
3. **Integrity**: A CRC16 is calculated over the header and payload.
4. **FEC Encoding**: The block is passed through a **Reed-Solomon RS(15,11)** encoder.
5. **Hardening**: Data is interleaved (spread out) and whitened (scrambled) to prevent long strings of 0s or 1s that confuse radio hardware.
6. **Bitstream**: The final bytes are expanded into raw bits, and a **Preamble** (clock recovery) and **Syncword** (unique signature) are prepended.

### C. The Physical Domain (`usrp_transceiver.py` & GNU Radio)
1. **Modulation**: Bits enter the GFSK or BPSK modulator.
2. **Tag Scaling**: A critical `packet_len` tag is attached to the stream. This tag tells the USRP hardware exactly when to start and stop the transmitter's power amplifier.
3. **RF Emission**: Samples are streamed over USB 3.0 to the USRP B205mini and hit the air at 915 MHz.

---

## 📂 3. Core Module Breakdown

| File | Developer's Perspective | RF Perspective |
| :--- | :--- | :--- |
| `usrp_transceiver.py` | The main "Orchestrator" and UI. | The SDR Front-End & Modulator. |
| `packetizer.py` | Data Serializer & Framer. | The Baseband TX Engine. |
| `depacketizer.py` | State Machine & Bit-Searcher. | The Baseband RX Engine. |
| `session_manager.py` | State-aware Handshake logic (TCP-like). | The MAC Layer (SYN/ACK). |
| `rs_helper.py` | Optimized math using Syndrome Tables. | Forward Error Correction (FEC). |
| `hop_generator_tod.py`| Cryptographic PRNG using AES. | FHSS Controller (Hopping). |

---

## 🔬 4. Critical Technical Concepts

### 🧩 PDU vs. Stream
GNU Radio uses two types of data: **Streams** (continuous flow of samples) and **PDUs** (discrete packets). 
Opal Vanguard uses **Asynchronous Message Passing** for most of the logic. This prevents the "GIL Lock" (Python's global interpreter lock) from freezing the radio during high-speed data bursts.

### 🔍 The "Blind Search" Engine (`depacketizer.py`)
Because the system is "Zero-Header" (no standard Wi-Fi headers), the receiver is always in a **SEARCH** state. 
- It uses a sliding **XOR bitmask** to look for the Syncword.
- In Python 3.10+, we use `.bit_count()` to calculate the **Hamming Distance** (how many bits are wrong). 
- If the distance is `<= 4`, the state machine transitions to **COLLECT** and starts harvesting bits.

### 🌪️ TOD Synchronization (`hop_generator_tod.py`)
Traditional frequency hopping requires a complex "Sync Channel." Opal Vanguard uses **Time-of-Day (TOD)**. 
- The AES-256 key is combined with the current Unix Second (Epoch).
- Both ALPHA and BRAVO calculate the exact same frequency for that specific second.
- **Developer Note**: This requires host system clocks to be NTP-synchronized within 50ms.

---

## 📶 5. Level 7: Differential-Frequency OFDM
Level 7 is the most advanced part of the codebase. It uses **Differential-Frequency OFDM (DF-OFDM)**.
- **Why?**: Standard OFDM requires perfect phase tracking. USRP oscillators "jolt" during frequency hops, which breaks standard OFDM.
- **The Solution**: We encode data as the phase transition *between* adjacent subcarriers. If the whole symbol shifts in phase, the *difference* between carriers remains the same.
- **The Scanner**: Since OFDM requires an aligned FFT window, the depacketizer emits a `scan_control` message every 100ms to shift the receiver's window by 1 sample until the syncword is found.

---

## 🛠️ 6. Evaluation Guide for Developers
When reviewing the code, look for:
1. **Thread Safety**: Notice how `PyQt5` signals are used to move data from the radio threads to the UI.
2. **Vectorization**: Observe how `rs_helper.py` and the `OFDMEqualizer` use NumPy arrays instead of Python loops to handle 2.0 Msps throughput.
3. **Tag Propagation**: Look at the `work()` functions in `usrp_transceiver.py` to see how `packet_len` tags are managed—this is the most common point of failure in SDR software.

---
*Opal Vanguard System Documentation v1.0 | Prepared for Software Engineering Evaluation*
