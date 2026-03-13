# Opal Vanguard: Developer Guide & Engineering Standards (v1.2)

This document outlines the core engineering principles, coding standards, and architectural patterns used in the Opal Vanguard project. Adhering to these standards ensures the link remains resilient, performant, and maintainable.

---

## 🛡️ 1. Modular Integrity (OSI Layer Decoupling)
The system is designed with strict decoupling between PHY, MAC, and Link layers. This allows for rapid waveform experimentation without destabilizing the protocol stack.

### Standards:
- **Sequential Processing**: Processing stages (COMSEC -> Header -> FEC -> Interleave -> Whiten) must be strictly sequential within the `packetizer` and `depacketizer`.
- **Initialization Efficiency**: Expensive DSP objects (Reed-Solomon codecs, AES ciphers, Interleaver tables) must be initialized in the `__init__` method. **NEVER** re-initialize these objects inside the `handle_msg` or `work` loops.
- **Config Driven**: Every architectural decision must be governed by the YAML configuration. Hard-coding mission parameters is strictly prohibited.

---

## ⚡ 2. The Super-Vectorized Engine (v15.8.12)
As a Python-based SDR, CPU cycles are our most precious resource. At 2.0 Msps, the radio has only 500ns to process each sample. To survive this, we use "Chunk-Based Processing" instead of "Bit-Based Loops."

### Implementation (The "Hot Path"):
- **NumPy Sliding Window**: The `depacketizer` uses NumPy vectorized array slices to search for syncwords. Instead of looping through bits in Python, we cast the incoming stream to a NumPy array and perform bitwise XOR operations across entire blocks.
- **Bulk Collection**: Once a syncword is detected, the system calculates the exact offset needed and captures the entire 120-byte tactical frame in a single memory slice (`in0[:needed]`). This offloads the work from Python to the C-optimized NumPy backend.
- **Native Bit-Counting**: Always use `(window ^ target).bit_count()` for Hamming distance. This uses the CPU's native popcount instruction, which is ~10x faster than string-based counting.

---

## 📡 3. High-Fidelity Hardware Timing
The USRP hardware relies on nanosecond-precise metadata (Tags) to control the RF front-end. We use a "Hardware-Native" approach to avoid the "Tag Gap" paradox.

### Standards:
- **C++ Native Scaling**: We utilize the native `blocks.tagged_stream_multiply_length` block positioned **AFTER** the modulator. This ensures that the `packet_len` tag is scaled from `bits` to `samples` at machine speed, preventing CPU-induced Underflows.
- **Modulator Filter Flushing**: Every burst is appended with a **2048-bit zero-tail** in the `packetizer`. This ensures that the modulator's internal FIR filter is completely flushed and the real CRC reaches the antenna before the USRP closes its transmission gate.
- **Timed Tuning**: Use UHD `set_command_time()` for frequency transitions. This offloads the hopping timing from the jittery Python scheduler to the USRP's internal FPGA clock.

---

## 🧵 4. Thread Safety & UI Concurrency
Opal Vanguard runs in a multi-threaded environment where GNU Radio (C++) and PyQt (Python) must interact safely.

### Standards:
- **Initialization Order**: Always initialize `Qt.QWidget` before `gr.top_block`. Swapping this order often stalls the radio thread pool and freezes the waterfall.
- **Message Bus Integrity**: Use `MessageProxy` for all telemetry. The proxy must pass raw PMT objects to the UI thread, where they are converted to Python standard types. Attempting to convert complex PMTs inside the high-speed radio thread causes event-loop starvation.
- **Unbuffered Terminal**: All tactical `print()` statements must use `flush=True` to ensure real-time visibility in the terminal without process-exit buffering.

---

## 🧪 5. Testing & Regression
Every "High-Level" feature must pass a "Low-Level" baseline check.

### Standards:
- **Level 0 (The Testbed)**: Use the `level0_test.yaml` config to isolate individual parameters (e.g., turning on FEC without Interleaving) to diagnose performance bottlenecks.
- **Hardware Simulation**: Run `python3 src/mission_sim.py` to verify that new code changes do not introduce `Tag Gaps` or `Underflows` before deploying to physical SDR hardware.

---
*Engineering Standards v1.2 | Opal Vanguard Technical Authority*

---

## 🐋 6. Containerization & Environment Parity
To ensure the high-performance C++ scaling and Super-Vectorized logic behave identically across different development machines, we use Docker.

### Standards:
- **Base Image**: Always use `ubuntu:24.04` to maintain compatibility with UHD 4.6+.
- **Hardware Access**: Containers must be run with `--privileged` and volume-mount `/dev/bus/usb` to allow the UHD driver to communicate with the B205mini.
- **X11 Forwarding**: To run the PyQt5 GUI from within a container, volume-mount `/tmp/.X11-unix` and pass the `DISPLAY` environment variable.
- **Compose Stack**: Use `docker-compose up` to launch both the `transceiver` and the `dashboard` simultaneously for a full tactical overview.
