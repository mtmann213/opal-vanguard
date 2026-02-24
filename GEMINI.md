# Project: Opal Vanguard
## Mission Profile
- **Goal:** Modular FHSS Messaging System.
- **Spectrum:** 900MHz ISM Band (902-928 MHz).
- **Modulation:** GFSK (start simple).
- **Hardware:** HackRF One.

## Technical Specifications
- **FHSS Logic:** Fibonacci LFSR for hop-sequence generation.
- **Whitening:** Fibonacci LFSR based on polynomial x^7 + x^4 + 1.
- **Packet:** Preamble (0xAAAA) -> Syncword (0x3D4C5B6A) -> Header -> Payload -> CRC16.
- **FEC:** Reed-Solomon.
- **Flowgraph:** GNU Radio 3.10+, utilizing Message Passing for frequency control to minimize latency.
