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
- Fibonacci LFSR-based frequency hopping.
- Reed-Solomon (15, 11) FEC.
- Fibonacci LFSR whitening (x^7 + x^4 + 1).
- Automatic Handshake and Session Management with seed synchronization.
