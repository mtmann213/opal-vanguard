# Opal Vanguard - Agent Documentation

## Project Overview
USRP-based SDR tactical data link system running at 2.0 Msps with frequency hopping, built on GNU Radio + PyQt.

## Quick Start

### Running Tests
```bash
cd /home/mannai/hermes/opal-vanguard
python3 -m pytest src/tests/ -v
```

To run GR-dependent tests (requires GNU Radio + USRP):
```bash
GR_AVAILABLE=true python3 -m pytest src/tests/ -v
```

### Running Transceiver
```bash
# GUI mode
python3 src/usrp_transceiver.py --role ALPHA --config mission_configs/level1_soft_link.yaml

# Headless mode
python3 src/usrp_headless.py --role ALPHA --config mission_configs/level1_soft_link.yaml
```

### Running Dashboard
```bash
python3 dashboard/app.py
# Then open http://localhost:5000
```

## Available Mission Levels

| Level | Config File | Features |
|-------|-------------|-----------|
| 0 | `level0_test.yaml` | All features enabled (testing) |
| 1 | `level1_soft_link.yaml` | Basic GFSK, no FEC |
| 2 | `level2_repairable.yaml` | GFSK + RS(15,11) FEC |
| 3 | `level3_resilient.yaml` | GFSK + FEC + Interleaving |
| 4 | `level4_stealth.yaml` | GFSK + DSSS (Barker) + Ghost mode |
| 5 | `level5_blackout.yaml` | GFSK + COMSEC + FHSS |
| 6 | `level6_link16.yaml` | MSK + CCSK + RS(15,11) (Link-16 style) |
| 7 | `level7_ofdm_master.yaml` | OFDM (WIP) |
| 8 | `level8_advanced.yaml` | GMSK/DQPSK options |
| 9 | `level9_deep_shadow.yaml` | CSS (Chirp Spread Spectrum, WIP) |

## Test Results

```
25 passed, 7 skipped (GR-dependent)
```

Skipped tests require GNU Radio runtime and USRP hardware.

## Key Configuration Fields

Every mission config should have these sections:
- `mission` — id, description
- `physical` — modulation, samp_rate, center_freq, samples_per_symbol, freq_dev
- `link_layer` — frame_size, use_fec, use_interleaving, use_whitening, use_nrzi, use_comsec, comsec_key
- `mac_layer` — arq_enabled, max_retries, amc_enabled
- `dsss` — enabled, type (Barker/CCSK), spreading_factor
- `hopping` — enabled, type, initial_seed, aes_key, fhss_key, num_channels, channel_spacing, dwell_time_ms
- `hardware` — args, tx_gain, rx_gain, tx_antenna, rx_antenna
- `application_layer` — payload_type, heartbeat_ms, src_id, dst_id

## Known Limitations

| Feature | Status | Notes |
|---------|--------|-------|
| RS3115 | Partial | Level 6 config specifies RS(31,15) but code uses RS(15,11). FEC works but not Link-16 spec compliant. |
| Barker DSSS | Not implemented | Config enables it but no spreading applied. Falls through to plain GFSK. |
| CSS Modulation | Not implemented | Level 9 specifies CSS but falls through to GFSK. |
| CRC32 | Not implemented | Level 7 config says CRC32 but code uses CRC16. Both sides agree so it works. |
| Level 7 FEC truncation | Potential issue | Large frame_size (940) with FEC produces output > frame_size, causing silent truncation. |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     usrp_transceiver.py                      │
│                         (GUI Node)                           │
├─────────────────────────────────────────────────────────────┤
│  session_manager ──► packetizer ──► pdu_to_tagged_stream   │
│       ▲                                                    │
│       │                                                    │
│  depacketizer ◄── pdu_from_tagged_stream ◄── usrp_source  │
└─────────────────────────────────────────────────────────────┘
```

- **PHY**: USRP hardware interface
- **Link**: packetizer/depacketizer (framing, FEC, CCSK)
- **MAC**: session_manager (handshake, ARQ)
- **Hop**: hop_generator_tod (AES-TOD frequency hopping)

## Debugging Tips

1. **No TX output**: Check USRP device args (`type=b200`)
2. **No RX sync**: Check syncword matches in configs
3. **FHSS not working**: Verify dwell_time_ms matches between nodes
4. **COMSEC failures**: Ensure comsec_key is identical on both nodes
5. **CRC errors**: Check for interference or gain settings

## Files of Interest

- `src/packetizer.py` — Frame encoding
- `src/depacketizer.py` — Frame decoding with async worker thread
- `src/session_manager.py` — MAC state machine
- `src/hop_generator_tod.py` — AES-TOD frequency hopping
- `src/dsp_helper.py` — DSP primitives (interleaver, scrambler, CCSK)
- `src/rs_helper.py` — Reed-Solomon FEC