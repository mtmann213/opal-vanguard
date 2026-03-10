# Opal Vanguard: Developer Guide & Engineering Standards

This document outlines the core engineering principles, coding standards, and architectural patterns used in the Opal Vanguard project. Adhering to these standards ensures the link remains resilient, performant, and maintainable.

---

## 🛡️ 1. Modular Integrity (OSI Layer Decoupling)
The system is designed with strict decoupling between PHY, MAC, and Link layers. This allows for rapid waveform experimentation without destabilizing the protocol stack.

### Standards:
- **Sequential Processing**: Processing stages (COMSEC -> Header -> FEC -> Interleave -> Whiten) must be strictly sequential within the `packetizer` and `depacketizer`.
- **Initialization Efficiency**: Expensive DSP objects (Reed-Solomon codecs, AES ciphers, Interleaver tables) must be initialized in the `__init__` method. **NEVER** re-initialize these objects inside the `handle_msg` or `work` loops.
- **Config Driven**: Every architectural decision must be governed by the YAML configuration. Hard-coding mission parameters is strictly prohibited.

---

## ⚡ 2. Performance & Vectorization (The "Hot Path")
As a Python-based SDR, CPU cycles are our most precious resource. At 2.0 Msps, the radio has only 500ns to process each sample.

### Standards:
- **Bitwise Math**: Use native Python 3.10+ bitwise operations (e.g., `int.bit_count()`, `^`, `&`) for synchronization and Hamming distance calculations. Avoid string conversions (`bin(x).count('1')`) in the data path.
- **NumPy First**: All mathematical operations on bit-arrays or IQ samples must be vectorized using NumPy. Avoid Python `for` loops for data manipulation.
- **Zero-Copy**: Minimize the conversion between PMT blobs and NumPy arrays. Use `pmt.u8vector_elements()` efficiently to access raw data.

---

## 🧵 3. Thread Safety & UI Concurrency
Opal Vanguard runs in a multi-threaded environment where GNU Radio (C++) and PyQt (Python) must interact safely without triggering the Global Interpreter Lock (GIL) or deadlocking.

### Standards:
- **Radio-to-UI (Downlink)**: Use the `MessageProxy` block to bridge GNU Radio message ports to `pyqtSignal(object)`. Never update a UI widget directly from a GNU Radio block method.
- **UI-to-Radio (Uplink)**: Use the **Asynchronous UI Bridge** (`manual_queue` + `UIBridge` block). The UI thread must only append to a thread-safe queue; the radio thread polls this queue to inject data.
- **Non-Blocking MAC**: Retuning and handshaking logic must be asynchronous. The UI should remain fluid even during a synchronization loss.

---

## 📡 4. Hardware Timing & Tag Precision
The USRP hardware relies on nanosecond-precise metadata (Tags) to control the RF front-end.

### Standards:
- **Tag Scaling**: If a block changes the number of samples (like interpolation/decimation), the `packet_len` tag must be scaled using `tagged_stream_multiply_length` BEFORE reaching the USRP Sink.
- **Hardware-Timed Hopping**: Use UHD `set_command_time()` for frequency transitions. This offloads the timing from the jittery Python scheduler to the USRP's internal FPGA clock.
- **Ghost Mode**: Ensure the `tx_sob` and `tx_eob` tags are correctly placed to trigger the Power Amplifier (PA) only during active bursts.

---

## 🧪 5. Testing & Regression
Every "High-Level" feature must pass a "Low-Level" baseline check.

### Standards:
- **The 18-Point Test**: Before pushing changes to `src/usrp_transceiver.py`, run `python3 src/test_all_configs.py` to ensure all 8 mission levels pass their digital loopback.
- **Sandbox Protocol**: New waveforms or complex logic must be verified in a standalone `verify_*.py` script before integration into the master transceiver.

---
*Engineering Standards v1.0 | Opal Vanguard Technical Authority*
