# Vanguard Data Factory (VDF)
**Branch:** `sidequest/vdf-factory`

## Overview
The VDF is a high-fidelity dataset generation suite designed to feed the `ai-rf` ResNet. It utilizes the "Hardware Trinity" (3x USRP B205-mini) to capture real-world RF snapshots with absolute ground truth metadata.

## Technical Standards
- **Snapshot Shape:** `(1024, 2)` (I/Q)
- **File Format:** HDF5 (Flat Dataset Structure)
- **Top-Level Keys:**
    - `X`: Raw Samples
    - `Y`: One-Hot Labels
    - `Z`: Metadata [SNR, CFO, SCO, SPS, Jamming_Active]
- **Synchronization:** 10ms CW Pilot Tone Cross-Correlation.

## Roadmap
- [ ] **Phase 0: Pilot** - 2 Modulations, 2,000 snapshots, pipeline verification.
- [ ] **Phase 1: Sequencer** - Master control of TX, RX, and Adversary nodes.
- [ ] **Phase 2: Full Sweep** - 30 Modulations, 500,000+ snapshots.

## Usage
*TBD after Phase 0 implementation.*
