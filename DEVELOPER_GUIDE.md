# Opal Vanguard: Developer Guide & Engineering Standards (v1.3)

This document outlines the core engineering principles, coding standards, and architectural patterns used in the Opal Vanguard project. Adhering to these standards ensures the link remains resilient, performant, and maintainable.

---

## 🛡️ 1. Modular Integrity (OSI Layer Decoupling)
The system is designed with strict decoupling between PHY, MAC, and Link layers. This allows for rapid waveform experimentation without destabilizing the protocol stack.

---

## ⚡ 2. The Super-Vectorized Engine (v15.8.22)
As a Python-based SDR, CPU cycles are our most precious resource. At 2.0 Msps, the radio has only 500ns to process each sample. 

### Implementation (The "Hot Path"):
- **NumPy Sliding Window**: The `depacketizer` uses NumPy vectorized array slices to search for syncwords.
- **CCSK Matrix LUT**: In Level 6, CCSK decoding is handled via a pre-calculated 32x32 Matrix LUT. Correlation is performed using a single `np.dot()` operation across the entire frame, bypassing all Python loops.
- **Bulk Collection**: Once a syncword is detected, the system captures the entire 120-byte tactical frame in a single memory slice.

---

## 📡 3. High-Fidelity Hardware Timing
The USRP hardware relies on nanosecond-precise metadata (Tags) to control the RF front-end.

### Standards:
- **C++ Native Scaling**: We utilize the native `blocks.tagged_stream_multiply_length` block positioned **AFTER** the modulator. 
- **Modulator Filter Flushing**: Every burst is appended with a **2048-bit zero-tail** in the `packetizer`. 
- **Timed Tuning**: Use UHD `set_command_time()` for frequency transitions.

---

## 🧵 4. Thread Safety & UI Concurrency
Opal Vanguard runs in a multi-threaded environment where GNU Radio (C++) and PyQt (Python) must interact safely.

### Standards:
- **Adaptive FPS**: High-CPU missions automatically drop UI rendering to **5 FPS** to preserve radio thread integrity.
- **Stealth Mode**: Operators can hide the waterfall widget entirely. This stops PyQt rendering calls and is the primary tool for stopping USRP Overflows (O) on lower-end hardware.
- **Message Bus Integrity**: Use `MessageProxy` for all telemetry. The proxy must pass raw PMT objects to the UI thread.

---

## 🐋 5. Containerization & Environment Parity
To ensure high performance, we use Docker with hardware passthrough.

### Standards:
- **Base Image**: Always use `ubuntu:24.04` for UHD 4.6+ parity.
- **Hardware Access**: Use `--privileged` and mount `/dev/bus/usb`.

---
*Engineering Standards v1.3 | Opal Vanguard Technical Authority*
