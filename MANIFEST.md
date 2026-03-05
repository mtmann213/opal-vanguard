title: The OPAL_VANGUARD OOT Module
brief: Modular FHSS Messaging System for 900MHz ISM
tags:
  - sdr
  - gnuradio
  - fhss
  - gfsk
author:
  - Michael Mann <michael.mann@opalvanguard.local>
copyright_owner:
  - Opal Vanguard Project
license: GPL-3.0-or-later
gr_supported_version: 3.10
---
Opal Vanguard is a Python-based GNU Radio framework for a modular Frequency Hopping Spread Spectrum (FHSS) messaging system. 

It implements a complete digital communication chain with:
- AES-CTR and TOD-Synced Frequency Hopping.
- Multiple Modulation Support (GFSK, MSK, PSK).
- Authentic Link-16 CCSK (32-chip) and DSSS (31-chip) spreading.
- Reed-Solomon (15, 11) and (31, 15) FEC.
- Fibonacci LFSR whitening (x^7 + x^4 + 1).
- Unified Mission Control via YAML tiered configs.
