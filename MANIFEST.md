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

## 🏭 5. Vanguard Data Factory (VDF) - HITL Dataset Generation

### `src/vdf/vdf_master.py`
- **Purpose**: Master Sequencer for the Hardware Trinity (3x USRP).
- **v3.3 Logic**: High-reliability harvest with hardware settling (1.0s), precise timing bridges, and live pilot injection for Zero-Drift synchronization.

### `src/vdf/vdf_capture.py`
- **Purpose**: High-Throughput Deep-Buffer Capture Engine (v2.13).
- **Features**: 
    - **Deep-Buffer Accumulator**: Gathers large sample blocks to handle 20ms pilots without stalling.
    - **Vectorized Search**: Optimized sliding-window correlation for real-time synchronization.
    - **Defensive-Write**: Absolute pathing and explicit flushing to ensure 100% data survival after system crashes.

### `src/vdf/vdf_mock_gen.py`
- **Purpose**: Industrial Archive Generator (v3.0).
- **Logic**: Implements Root-Raised Cosine (RRC) and Gaussian pulse shaping for mathematically perfect baseband "Ground Truth."

### `src/vdf/vdf_repair.py`
- **Purpose**: Surgical Repair Engine (v1.1).
- **Logic**: Targets missing mode combinations using ultra-sensitive 0.05 correlation triggers and 40s patient search windows to ensure 100% dataset coverage.

## 🌒 6. Mission: Specter's Edge (Operational Robustness)

### `src/specter_sequencer.py`
- **Purpose**: Multi-Dimensional Diversity Harvest Engine (v1.7).
- **Nested Loops**: Sweeps 24 Classes x 4 Gains x 3 SCO Drift levels x 3 CFO Offsets to generate a high-resiliency dataset for field-ready models.

### `src/vdf/live_monitor.py`
- **Purpose**: Real-time HDF5 Telemetry Watchtower (v1.0).
- **Features**: Visualizes constellations and peak-power stats live using SWMR mode to audit the harvest as it hits the disk.

### `src/vdf/grid_viewer.py`
- **Purpose**: Snapshot Evolution Auditor (v1.0).
- **Logic**: Generates 5x5 grids of sequential snapshots to visualize signal drift and quality across time.

### `src/vdf/visual_diagnostics.py`
- **Purpose**: Tactical Signal Auditor (v1.1).
- **Features**: Joint Constellation/Phase Trajectory plots for surgical verification of individual snapshots.

### `src/vdf/power_diagnostic.py`
- **Purpose**: Signal-vs-Noise Discriminator (v1.0).
- **Logic**: Uses power histograms and phase trajectories to distinguish between actual hardware signals and amplified thermal noise.

---
*Manifest v1.6 | Opal Vanguard Technical Authority*
