# Opal Vanguard: Technical Source Manifest (v1.2)

This document provides a comprehensive technical overview of every source file in the Opal Vanguard project. It is designed to assist developers in understanding the architectural relationships and individual responsibilities of each component.

---

## 🛰️ 1. Core Transceivers (Physical Layer Entry Points)

### `src/usrp_transceiver.py`
- **Purpose**: The primary GUI-based application for physical node operation.
- **v15.9.5 Architecture**:
    - **Stealth Mode**: Pause waterfall rendering to free ~30% CPU.
    - **Hardware Guard**: Explicit USB interface cleanup to prevent claim errors.
    - **Precision Buffering**: 8192-item hardware buffers for GIL stability.

### `src/usrp_headless.py`
- **Purpose**: Terminal-only node for simulations and remote servers.

---

## 🛠️ 2. High-Speed DSP & Link Layer (The "Hot Path")

### `src/packetizer.py`
- **Purpose**: Bit-perfect framing and hardening.
- **Features**: Dynamic syncword/preamble support + 2048-bit flush tail.

### `src/depacketizer.py`
- **Purpose**: Asynchronous recovery engine (v15.9.2+).
- **Architecture**:
    - **Threaded Offload**: Syncword search runs in the radio thread; CCSK/FEC math runs in a background `threading.Thread`.
    - **Fully Vectorized CCSK**: Symbol recovery via matrix-matrix multiplication (`np.dot`).
    - **Sliding Window Search**: NumPy convolution-style syncword detection.

### `src/dsp_helper.py`
- **Purpose**: Vectorized math primitives. Contains the Matrix LUT for CCSK decoding.

---

## 🧠 3. MAC & Application Layers

### `src/session_manager.py`
- **Purpose**: Autonomous state machine.
- **v15.9.3 Logic**: Random-Backoff SYN pulses to prevent handshake collisions.

---

## 🧪 4. Testing & Validation

### `src/test_full_suite.py`
- **Purpose**: 9-point regression suite covering Link Layer logic and PHY Timing.

---
*Manifest v1.2 | Opal Vanguard Technical Authority*
