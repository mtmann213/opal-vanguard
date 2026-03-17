# VDF Implementation Guide: Project Opal Vanguard
**Technical Specifications for hardware-based dataset generation.**

## 1. Data Schema
*   **Shape:** `(N, 1024, 2)`
*   **Structure:** Flat datasets (`X`, `Y`, `Z`) for O(1) random access during training.
*   **Metadata (Dataset Z):** Expanded to 8 columns: `[SNR, Intentional_CFO, Measured_HW_CFO, SPS, Jam_Active, Env_ID, Jam_Type, Hardware_Gain]`.

## 2. Signal Generation
*   **Bridge:** Pre-compute Sionna or NumPy RRC-filtered waveforms on the GPU/Frontend node.
*   **Format:** Export as `.npy` files for the USRP sequencer to consume.
*   **Industrial Hardening:** Apply on-the-fly **SCO (Symbol Clock Offset)** resampling to simulate clock jitter across the Hardware Trinity.

## 3. Synchronization & Calibration
*   **Pilot Tone:** 40ms CW burst (50kHz offset) at the start of every capture session.
*   **FFT-Lock (v2.32):** Use frequency-domain peak detection to identify the brightest peak in the pilot spectrum for sub-Hz frequency estimation.
*   **Auto-Leveler AGC (v2.33):** Implement real-time Automatic Gain Control to scale attenuated hardware signals to the 0.8 digital amplitude range.
*   **The Despinner:** Apply `np.exp(-1j * 2 * np.pi * offset * t)` correction to every snapshot to eliminate "Hollow Donuts" and reveal distinct PSK/QAM clusters.

## 4. Adversary Control
*   **Coordination:** Master Sequencer must trigger USRP #3 via ZMQ/TCP message ports.
*   **Tagging:** Only mark snapshots as "Jammed" if the Adversary USRP confirms the TX-Start ack.

## 5. Acclimation Prep
*   **Pilot Run:** First capture should be <100MB (2 classes) to verify the HDF5-to-ResNet pipeline.
*   **Normalization:** The `VDF_Receiver` must apply the `x/(1+|x|)` Soft-Clip before saving to match the training baseline.
