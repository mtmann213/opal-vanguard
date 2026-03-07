# Opal Vanguard - Field Terminal User Manual

## 📖 Introduction
The Opal Vanguard Field Terminal is a high-performance software-defined radio (SDR) transceiver designed for resilient, secure, and stealthy messaging. This manual covers operation, troubleshooting, and provides a deep-dive glossary of the system's core technologies.

---

## 🎮 Basic Operation
### 1. Synchronization
Ensure both laptops are connected to a shared network (or the Internet) to synchronize their system clocks. This is **critical** for Level 5+ Time-of-Day (TOD) frequency hopping.

### 2. Launching the Terminal
Run the transceiver using the mission configuration for your current level:
```bash
sudo -E python3 src/usrp_transceiver.py --role ALPHA --serial <YOUR_SERIAL> --config mission_configs/level5_blackout.yaml
```

### 3. Tuning the Link
- **Waterfall**: Use the Spectrum Waterfall to monitor signal presence.
- **RX Gain**: If the waterfall is solid yellow, **lower the RX gain** until the background is dark blue.
- **Signal Scope**: Use the scope to verify the bit-level recovery. A clean square wave indicates a strong signal lock.

---

## 📚 Technical Glossary & Concepts

### FHSS (Frequency Hopping Spread Spectrum)
A method of transmitting radio signals by rapidly switching a carrier among many frequency channels.
- **Why it matters**: It makes the signal extremely difficult to intercept or jam, as the "target" frequency is constantly moving based on a pseudo-random sequence.
- **Opal Vanguard Implementation**: We use AES-based pseudo-random sequences synchronized via Time-of-Day (TOD).

### DSSS (Direct Sequence Spread Spectrum)
A modulation technique where the transmitted signal takes up more bandwidth than the information signal that is being modulated.
- **Why it matters**: It "spreads" the signal power into the noise floor, making it nearly invisible to standard scanners (Low Probability of Intercept) and highly resistant to narrow-band jamming.
- **Chips**: The small sub-bits used to spread each information bit. The number of chips per bit is the **Spreading Factor (SF)**.

### COMSEC (Communications Security)
The discipline of preventing unauthorized interceptors from accessing telecommunications in an intelligible form.
- **AES-CTR**: We use Advanced Encryption Standard in Counter mode. This is a "stream cipher" that is highly resilient to RF bit errors; a single corrupted bit in the air only ruins one character of the message rather than the whole packet.

### FEC (Forward Error Correction)
A technique used for controlling errors in data transmission over unreliable or noisy communication channels.
- **Reed-Solomon (RS)**: A powerful mathematical algorithm that adds redundant data to each packet. Our RS(15,11) implementation can automatically "repair" up to 2 corrupted bytes in every 15-byte block without needing a retransmission.

### ARQ (Automatic Repeat Request)
An error-control method for data transmission that uses acknowledgments (ACKs) and timeouts to achieve reliable data transmission.
- **Logic**: If a receiver hears a packet but the CRC fails (and FEC can't fix it), the transmitter will automatically resend the data up to the `max_retries` limit.

### NRZI (Non-Return-to-Zero Inverted)
A method of mapping binary signals to physical pulses.
- **Why it matters**: In RF, the phase of a signal can sometimes be inverted (180 degrees) by the environment. NRZI only cares about *changes* in state, making the link immune to phase-flip corruption.

### Whitening (Scrambling)
The process of XORing the data stream with a pseudo-random sequence before transmission.
- **Why it matters**: Radio hardware struggles to transmit long strings of identical bits (e.g., all 0s). Whitening ensures the signal is always "randomized," which keeps the hardware's DC-offset balanced and the link stable.

### Interleaving
A process of rearranging data in a non-contiguous way.
- **Why it matters**: RF interference often happens in "bursts" that kill several consecutive bits. Interleaving spreads those bits out across the packet so that, after de-interleaving, the errors appear as isolated single-bit flips that the FEC can easily repair.

---

## 🛠 Troubleshooting
| Issue | Potential Cause | Solution |
|-------|----------------|----------|
| Blank Waterfall | USRP Stall / USB Hub | Restart the script; ensure USRP is on a USB 3.0 port. |
| Solid Yellow Waterfall | Gain Saturation | Lower the **RX Gain** slider immediately. |
| [CRC FAIL] | High Noise / Multipath | Increase **TX Gain** or move antennas; check for local 900MHz interference. |
| Decryption failed | Key Mismatch / High BER | Ensure `comsec_key` matches on both ends; lower gain to reduce saturation. |
| No SYN/ACK | Clock Drift | Run `ntpdate` or check system time sync on both laptops. |
