# Opal Vanguard: Mission Configuration Guide (v10.2)

This guide provides a detailed technical breakdown of every parameter used in the `mission_configs/` YAML files. Use this as a reference for tuning the system or understanding the progression of mission difficulties.

---

## 1. Mission Metadata
- **`id`**: A unique identifier for the mission level (e.g., `LEVEL_7_OFDM_MASTER`). This triggers internal logic shifts such as larger packet buffers (1024 bytes) and high-speed syncword detection.

## 2. Physical Layer (`physical`)
- **`modulation`**:
  - `GFSK`: Gaussian Frequency Shift Keying (Baseline). 
  - `DBPSK` / `DQPSK`: Used for robust tactical modes.
  - `OFDM`: **Orthogonal Frequency Division Multiplexing** (Level 7). High-speed, multi-carrier data link.
- **`samp_rate`**: The number of samples per second (Hz). 
  - **Level 7 Standard**: 2,000,000 (2.0 Msps).
- **`center_freq`**: The base frequency in Hz (e.g., 915,000,000 for the 900MHz ISM band).
- **`samples_per_symbol (sps)`**: For OFDM, this determines the symbol duration relative to the sample rate.
- **`ghost_mode`**: (Level 4+) Enables "Stealth" transmission. The hardware powers down the TX amplifier between bursts.

## 3. Link Layer (`link_layer`)
- **`use_whitening`**: Scrambles the data stream to prevent DC offset imbalances.
- **`use_interleaving`**: Matrix Interleaver. For Level 7, the `interleaver_rows` should be increased to **64** to handle larger packet sizes (1024 bytes).
- **`use_fec`**: Enables **RS(15,11)** Forward Error Correction. Repairs up to 2 symbols per block.
- **`use_comsec`**: Enables **AES-CTR** encryption.
- **`crc_type`**: 
  - `CRC16`: Used for smaller Level 1-5 packets.
  - `CRC32`: Recommended for Level 7 OFDM to prevent collisions in high-speed data.

## 4. MAC Layer (`mac_layer`)
- **`amc_enabled`**: Adaptive Modulation and Coding (Auto-tuning).
- **`afh_enabled`**: Adaptive Frequency Hopping (Jammer evasion).

## 5. DSSS Layer (`dsss`)
- **`type`**: 
  - `Barker`: Standard 11-chip DSSS.
  - `CCSK`: **Cyclic Code Shift Keying** (32-chip). Modern tactical spreading used in Level 6 and 7.

## 6. Hopping Layer (`hopping`)
- **`type`**: `AES` (Pseudo-random sequence generated via AES-256).
- **`sync_mode`**: `TOD` (**Time-of-Day**). Absolute Unix timestamp-based synchronization (Critical for Level 5+).
- **`dwell_time_ms`**: Time spent on each frequency hop. Standard is 1000ms (1 second).

## 7. Hardware (`hardware`)
- **`tx_gain` / `rx_gain`**: USRP power levels (0-90 dB). 
- **`tx_antenna` / `rx_antenna`**: Physical ports (e.g., `TX/RX`).
