# Project: Opal Vanguard
## Mission Profile
- **Goal:** Modular, Secure FHSS Messaging System.
- **Spectrum:** 900MHz ISM Band (902-928 MHz).
- **Modulation:** GFSK (Baseline) / DBPSK (Tactical).
- **Hardware:** USRP B205mini.

## Technical Specifications
- **FHSS Logic**: AES pseudo-random hop sequences synchronized via TOD.
- **COMSEC**: AES-CTR encryption for error-tolerant secure data.
- **Syncword**: 0x3D4C5B6A with Hamming Distance detection (2-bit error tolerance).
- **Burst Logic**: Start-of-Burst (SOB) and End-of-Burst (EOB) hardware tagging.
- **FEC**: Reed-Solomon RS(15,11) self-healing data blocks.
- **Flowgraph**: GNU Radio 3.10+, utilizing Asynchronous Message Passing for frequency control.
