# Opal Vanguard: Mission Configuration Guide

This guide provides a detailed technical breakdown of every parameter used in the `mission_configs/` YAML files. Use this as a reference for tuning the system or understanding the progression of mission difficulties.

---

## 1. Mission Metadata
- **`id`**: A unique identifier for the mission level (e.g., `LEVEL_5_BLACKOUT`). Used by the transceiver to set specific logic modes (like packet lengths).

## 2. Physical Layer (`physical`)
- **`modulation`**: The digital modulation scheme.
  - `GFSK`: Gaussian Frequency Shift Keying (Absolute Baseline). Reliable and simple.
  - `DBPSK` / `DQPSK`: Differential Phase Shift Keying. Used for higher resilience in DSSS modes.
  - `OFDM`: Orthogonal Frequency Division Multiplexing. High-speed, multi-carrier mode (Level 7).
- **`samp_rate`**: The number of samples per second (Hz). 
  - **Standard**: 2,000,000 (2 Msps).
  - **N150 Optimized**: 1,000,000 (1 Msps) for advanced levels to prevent CPU overflows.
- **`center_freq`**: The base frequency in Hz (e.g., 915,000,000 for the 900MHz ISM band).
- **`samples_per_symbol (sps)`**: The number of samples used to represent one bit. 
  - **Stability Baseline**: 10. Provides high resolution for burst timing.
- **`freq_dev`**: (GFSK only) The frequency deviation in Hz. 
  - **Winning Baseline**: 25,000 (25 kHz). Provides narrow signal for better SNR.
- **`ghost_mode`**: (Level 4+) Enables "Stealth" transmission. The radio hardware physically powers down the TX amplifier between packets to minimize the RF footprint.

## 3. Link Layer (`link_layer`)
- **`use_whitening`**: Enables an LFSR-based scrambler. Prevents DC offset issues.
- **`use_interleaving`**: Enables a Matrix Interleaver to protect against burst errors.
- **`use_fec`**: Enables Forward Error Correction.
  - Standard levels use **RS(15,11)**: Can fix 2 corrupted bytes per block.
- **`use_nrzi`**: Enables Non-Return-to-Zero Inverted encoding for phase-flip immunity.
- **`use_comsec`**: (Level 5+) Enables **AES-CTR** encryption for the mission payload.
- **`comsec_key`**: The 256-bit hex key used for encryption.

## 4. MAC Layer (`mac_layer`)
- **`arq_enabled`**: Enables Automatic Repeat Request (SYN/ACK/NACK logic).
- **`max_retries`**: The number of times the MAC layer will attempt to resend a failed packet.
- **`afh_enabled`**: Enables Adaptive Frequency Hopping (Level 6).
- **`amc_enabled`**: Enables Adaptive Modulation and Coding.

## 5. DSSS Layer (`dsss`)
- **`enabled`**: Enables Direct Sequence Spread Spectrum.
- **`spreading_factor (sf)`**: The number of "chips" per bit. Standard is 31.

## 6. Hopping Layer (`hopping`)
- **`enabled`**: Enables Frequency Hopping (FHSS).
- **`type`**: `AES` (pseudo-random) or `LFSR`.
- **`sync_mode`**: `TOD` (Time-of-Day) or `HANDSHAKE`.
- **`dwell_time_ms`**: Stay-time on one frequency. Standard is 1000ms.
- **`num_channels`**: The size of the hop-set.
- **`channel_spacing`**: The distance in Hz between each hop channel.
  - **1 Msps Optimization**: 40,000 Hz spacing for 20 channels.

## 7. Hardware (`hardware`)
- **`tx_gain` / `rx_gain`**: Power levels for the USRP (0-90 dB). 
- **`tx_antenna` / `rx_antenna`**: Physical ports. Default is `TX/RX` for half-duplex.
