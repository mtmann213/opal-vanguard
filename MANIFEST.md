# Opal Vanguard: Technical Source Manifest (v1.0)

This document provides a comprehensive technical overview of every source file in the Opal Vanguard project. It is designed to assist developers in understanding the architectural relationships and individual responsibilities of each component.

---

## 🛰️ 1. Core Transceivers (Physical Layer Entry Points)

### `src/usrp_transceiver.py`
- **Purpose**: The primary GUI-based application for physical node operation.
- **Basics**: A GNU Radio `top_block` integrated with a PyQt5 event loop. It manages the high-speed sample flow between the hardware (USRP) and the protocol logic.
- **Key Logic**:
    - **Standardized Initialization**: Uses a specific `QWidget -> top_block` sequence to prevent thread deadlocks.
    - **Timed Tuning**: Implements hardware-timed frequency hopping using UHD `set_command_time`.
    - **Message Bus**: Uses `MessageProxy` blocks to bridge raw PMT data from GNU Radio threads to the Python UI thread safely.
- **Interactions**: Loads `packetizer`, `depacketizer`, `session_manager`, and `hop_generator_tod`.

### `src/usrp_headless.py`
- **Purpose**: A terminal-only version of the transceiver for remote deployments and simulations.
- **Basics**: Functionally identical to the GUI version but stripped of PyQt5 dependencies.
- **Interactions**: Core component for `src/mission_sim.py`.

---

## 🛠️ 2. High-Speed DSP & Link Layer (The "Hot Path")

### `src/packetizer.py`
- **Purpose**: Transforms raw application messages into hardware-ready bitstreams.
- **Basics**: Sequential processing: `Header Injection -> RS-FEC -> Interleaving -> Whitening -> Preamble/Syncword Attachment`.
- **Developer Note**: Implements **2048-bit Flush Padding** to ensure the modulator filter is empty before the hardware gate closes.

### `src/depacketizer.py`
- **Purpose**: Recovers structured data from a noisy, continuous bitstream.
- **Basics**: Implements the **Super-Vectorized Engine (v15.8.12)**. Uses a NumPy sliding window to perform high-speed bitwise XOR searches for the syncword.
- **Key Logic**:
    - **Bulk Collection**: Captures whole memory slices once a sync is found, bypassing Python's loop overhead.
    - **Adaptive Threshold**: Automatically scales Hamming Distance tolerance based on syncword length.

### `src/dsp_helper.py`
- **Purpose**: Collection of vectorized math primitives for the link layer.
- **Contents**:
    - `MatrixInterleaver`: High-speed NumPy transpose/reshape for burst error protection.
    - `Scrambler`: LFSR-based whitening to remove DC bias from the signal.
    - `NRZIEncoder`: Differential encoding to protect against 180-degree phase flips.
    - `CCSKProcessor`: 32-chip Cyclic Code Shift Keying for Level 6/Link-16 spreading.

### `src/rs_helper.py`
- **Purpose**: Implementation of the Reed-Solomon (15,11) Self-Healing code.
- **Basics**: Works at the 4-bit nibble level. Can repair up to 2 corrupted nibbles per 15-nibble block.

---

## 🧠 3. Logic & Session Management (MAC Layer)

### `src/session_manager.py`
- **Purpose**: Manages node handshakes, state persistence, and ARQ (Automatic Repeat Request).
- **Basics**: A state machine (`SEARCHING -> CONNECTING -> CONNECTED`).
- **Key Logic**:
    - Handles **ACK/NACK** generation for reliable data delivery.
    - Manages the cryptographic **Seed Sync** for hopping alignment.

### `src/hop_generator_tod.py`
- **Purpose**: Cryptographically secure, time-synchronized frequency selection.
- **Basics**: Uses AES-CTR logic to turn the current Unix Epoch time into a pseudo-random channel index.
- **Interactions**: Emits dictionary-based tuning messages (`freq` and `time`) to the transceiver's `UHDHandler`.

### `src/hop_generator_aes.py`
- **Purpose**: Legacy AES-based hopping for environments where absolute Time-of-Day is not available.

---

## 🧪 4. Testing, Simulation & Validation

### `src/mission_sim.py`
- **Purpose**: Multi-node hardware-in-the-loop simulation.
- **Basics**: Launches two instances of `usrp_headless.py` (ALPHA and BRAVO) using local loopback or physical hardware to verify end-to-end mission success.

### `src/test_all_configs.py`
- **Purpose**: The "Opal Vanguard" 18-point regression suite.
- **Basics**: Rapidly cycles through every mission YAML to verify mathematical logic accuracy.

### `src/config_validator.py`
- **Purpose**: Sanitizes mission YAMLs before they reach the transceivers. Ensures parameters like `frame_size` and `interleaver_rows` are mathematically compatible.

---

## 📊 5. Operations & Visualization

### `dashboard/app.py`
- **Purpose**: Web-based "Commander's View" for remote monitoring.
- **Basics**: A Flask application that reads local radio logs and visualizes Link Quality (LQI) and Message Throughput.

---

## 🧩 Architectural Inter-Dependency Map

1.  **Startup**: `usrp_transceiver.py` loads a YAML mission config.
2.  **Validation**: `config_validator.py` ensures the math is sound.
3.  **Physical Link**: `usrp_transceiver` initializes the B205mini and the `UHDHandler`.
4.  **MAC Loop**: `session_manager.py` triggers `mac_strobe`.
5.  **Transmission**:
    - Data flows to `packetizer.py` (Link Layer).
    - Bitstream flows through `mod_a` -> `mult_len` -> `usrp_sink` (PHY Layer).
6.  **Hopping**: `hop_generator_tod.py` updates frequencies every `dwell_time_ms`.
7.  **Reception**:
    - Bits from `demod_b` flow into `depacketizer.py`.
    - `depacketizer.py` uses the **Super-Vectorized Engine** to find data.
    - Recovered payloads are dispatched to the UI and `session_manager.py` for ACK processing.

---
*Manifest v1.0 | Opal Vanguard Technical Authority*
