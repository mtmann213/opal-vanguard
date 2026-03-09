# Opal Vanguard: Project Resume & Status (v11.5)

## 📡 Current Status: EMERGENCY BASELINE RECOVERY
The project successfully implemented a complex **Differential-Frequency OFDM** link (Level 7), but the architectural changes (Packed-PDU transition and Tag Scaling) caused a regression in the Level 1-6 GFSK/BPSK baseline. The current main build is "silent" (no RF energy leaving the antennas).

### ✅ Hardware Verification
- **Devices**: Both USRP B205minis (3449AC1, 3457464) are healthy and identified over USB 3.0.
- **RF Path**: Confirmed functional at 915 MHz using `hw_smoke_test.py`. Hardware is NOT the issue.
- **Last Known Working**: Code in `/home/dev2/opal-vanguard/last_night/` is verified working for Levels 1-6.

### 🔬 Technical Roadblocks
1. **RF Blackout**: In Level 1, no signal is visible in Inspectrum. Likely caused by a "Tag Paradox" where the USRP sink truncates the burst because the `packet_len` tag doesn't match the samples-per-symbol (SPS) expansion.
2. **PDU Mismatch**: The transition from raw bits to packed bytes for OFDM confused the GFSK modulators.
3. **Ghost Hopping**: The UHD frequency handler was occasionally listening to the TOD generator even when hopping was disabled.

### 🛠️ Restoration Strategy (Immediate Priority)
1. **Surgical Reversion**: Revert the GFSK/BPSK pathways in `src/usrp_transceiver.py` to the exact bit-stream architecture used in `last_night/src/usrp_transceiver.py`.
2. **Modular Packetizer**: Ensure `src/packetizer.py` uses:
   - **GFSK/BPSK**: 512-bit preamble, 32-bit sync, raw bit output.
   - **OFDM**: 1034-bit preamble, 64-bit sync, packed byte output.
3. **Validation**: Run `ALPHA` and `BRAVO` on Level 1 until `[OK]` heartbeats return at 915 MHz before touching Level 7 again.

### 🚀 Next Steps for Level 7 (Once Baseline is Fixed)
- Integrate the **Symbol-Aligned DF-OFDM** (47 data carriers + 1 phase anchor).
- Utilize the **Continuous Phase Transition** search in the depacketizer to solve the synchronization lag.

---
*Resume point created: Sunday, March 8, 2026. Ready for system restart if necessary.*
