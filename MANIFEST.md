# Opal Vanguard: Technical Source Manifest (v1.1)

This document provides a comprehensive technical overview of every source file in the Opal Vanguard project. It is designed to assist developers in understanding the architectural relationships and individual responsibilities of each component.

---

## 🛰️ 1. Core Transceivers (Physical Layer Entry Points)

### `src/usrp_transceiver.py`
- **Purpose**: The primary GUI-based application for physical node operation.
- **v15.8.22 Features**:
    - **Stealth Mode**: A UI toggle that pauses waterfall rendering to free ~30% CPU, eliminating USRP Overflows (O) on lower-end hardware.
    - **Precision Buffering**: Increased hardware source buffers to 8192 to stabilize GIL contention.
    - **Timed Tuning**: Nanosecond-precise hopping via UHD `set_command_time`.

### `src/usrp_headless.py`
- **Purpose**: Terminal-only node for simulations and remote servers. Synchronized with the v15.8.22 performance engine.

---

## 🛠️ 2. High-Speed DSP & Link Layer (The "Hot Path")

### `src/packetizer.py`
- **Purpose**: Bit-perfect framing and hardening.
- **Logic**: Header -> RS-FEC -> Interleaving -> Whitening -> 2048-bit Filter Flush Tail.

### `src/depacketizer.py`
- **Purpose**: High-speed recovery engine.
- **v15.8.22 Logic**:
    - **Intelligent Clock Recovery**: Leverages demodulator native sync to achieve 90% CPU reduction.
    - **Fully Vectorized CCSK**: Decodes tactical symbols using single Matrix-Matrix multiplications (`np.dot`).
    - **Sliding Window Search**: NumPy convolution-style syncword detection.

### `src/dsp_helper.py`
- **Purpose**: Vectorized math library. Contains the CCSK Matrix LUT and Matrix Interleaver primitives.

---

## 🧠 3. MAC & Application Layers

### `src/session_manager.py`
- **Purpose**: Reliable delivery (ARQ) and state machine management.

### `src/hop_generator_tod.py`
- **Purpose**: Cryptographically secure time-synced hopping.

---

## 🧪 4. Testing & Validation

### `src/test_full_suite.py`
- **Purpose**: 9-point regression suite covering Link Layer logic and PHY Timing.

---
*Manifest v1.1 | Opal Vanguard Technical Authority*
