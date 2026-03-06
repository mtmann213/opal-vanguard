# Opal Vanguard: Mission Configuration Guide

This guide provides a detailed technical breakdown of every parameter used in the `mission_configs/` YAML files. Use this as a reference for tuning the system or understanding the progression of mission difficulties.

---

## 1. Mission Metadata
- **`id`**: A unique identifier for the mission level (e.g., `LEVEL_3_RESILIENT`). Used by the transceiver to set specific logic modes (like packet lengths).

## 2. Physical Layer (`physical`)
- **`modulation`**: The digital modulation scheme.
  - `GFSK`: Gaussian Frequency Shift Keying (Default). Reliable and simple.
  - `DBPSK` / `DQPSK`: Differential Phase Shift Keying. More spectrally efficient but sensitive to phase noise.
  - `MSK`: Minimum Shift Keying. Continuous phase modulation for lower interference.
  - `OFDM`: Orthogonal Frequency Division Multiplexing. High-speed, multi-carrier mode (Level 7).
- **`samp_rate`**: The number of samples per second (Hz). 2,000,000 (2 Msps) is standard. Reducing this to 1,000,000 can help slower CPUs handle the signal processing.
- **`center_freq`**: The base frequency in Hz (e.g., 915,000,000 for the 900MHz ISM band).
- **`samples_per_symbol (sps)`**: The number of samples used to represent one bit. Higher values (e.g., 8 or 10) improve reliability at the cost of speed.
- **`freq_dev`**: (GFSK only) The frequency deviation in Hz. Determines how far the frequency shifts for a '1' vs a '0'.
- **`ghost_mode`**: (Level 4+) Enables "Stealth" transmission. The radio hardware physically powers down the TX amplifier between packets to minimize the RF footprint.

## 3. Link Layer (`link_layer`)
- **`use_whitening`**: Enables an LFSR-based scrambler. Prevents long strings of 0s or 1s from causing DC offset issues in the radio hardware.
- **`use_interleaving`**: Enables a Matrix Interleaver. Spreads out data so that a burst of interference only causes isolated bit errors rather than destroying an entire block of data.
- **`interleaver_rows`**: The depth of the interleaver. More rows = better protection against long interference bursts.
- **`use_fec`**: Enables Forward Error Correction.
  - Standard levels use **RS(15,11)**: Reed-Solomon encoding that can repair up to 2 corrupted bytes per block.
- **`use_nrzi`**: Enables Non-Return-to-Zero Inverted encoding. Makes the signal immune to 180-degree phase inversions (common in RF).
- **`use_manchester`**: Enables Manchester encoding. Ensures a transition in every bit for perfect clock recovery, but halves the effective data rate.
- **`use_comsec`**: (Level 5+) Enables AES-GCM encryption for the payload.
- **`comsec_key`**: The 256-bit hex key used for encryption.

## 4. MAC Layer (`mac_layer`)
- **`arq_enabled`**: Enables Automatic Repeat Request. If a packet's CRC fails, the receiver stays silent, and the transmitter will automatically resend the packet.
- **`max_retries`**: The number of times the MAC layer will attempt to resend a failed packet before giving up.
- **`afh_enabled`**: Enables Adaptive Frequency Hopping (Level 6). The system will "blacklist" frequencies that consistently fail CRC and stop hopping to them.
- **`amc_enabled`**: Enables Adaptive Modulation and Coding. The system will automatically drop to a simpler modulation (e.g., GFSK) if the link quality becomes critical.

## 5. DSSS Layer (`dsss`)
- **`enabled`**: Enables Direct Sequence Spread Spectrum (Level 4).
- **`spreading_factor (sf)`**: The number of "chips" per bit. A factor of 31 means one bit is spread across 31 chips, providing massive resistance to jamming.
- **`chipping_code`**: The specific pseudo-noise sequence used to spread the signal. Both radios must have matching codes.

## 6. Hopping Layer (`hopping`)
- **`enabled`**: Enables Frequency Hopping (Level 5).
- **`type`**:
  - `LFSR`: Simple Fibonacci generator.
  - `AES`: Cryptographically secure hopping sequence based on an AES key.
- **`sync_mode`**:
  - `HANDSHAKE`: Radios sync sequences during the initial SYN/ACK.
  - `TOD`: Time-of-Day sync (Level 6). Radios sync based on a shared clock.
- **`dwell_time_ms`**: How long (in milliseconds) the radio stays on one frequency before hopping to the next.
- **`num_channels`**: The size of the hop-set (e.g., 50 channels).
- **`channel_spacing`**: The distance in Hz between each hop channel (e.g., 150,000 Hz).

## 7. Hardware (`hardware`)
- **`tx_gain` / `rx_gain`**: Power levels for the USRP (0-90 dB). 
- **`tx_antenna` / `rx_antenna`**: Which physical port to use. `TX/RX` is standard for half-duplex.
- **`args`**: Low-level UHD device arguments (e.g., `type=b200`).
