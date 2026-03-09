#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Hopping Logic Verification

import os
import sys
import time
import pmt
import struct
import numpy as np

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hop_generator_aes import aes_hop_generator
from hop_generator_tod import tod_hop_generator
from hop_controller import lfsr_hop_generator

def test_aes_hopping():
    print("--- [TEST] AES-CTR Hopping ---")
    key = b'\x00' * 32
    num_channels = 50
    center_freq = 915e6
    spacing = 150e3
    
    hop = aes_hop_generator(key=key, num_channels=num_channels, center_freq=center_freq, channel_spacing=spacing)
    
    # Mock message_port_pub to capture frequencies
    freqs = []
    def mock_pub(port, msg):
        freqs.append(pmt.to_double(msg))
    hop.message_port_pub = mock_pub
    
    # Trigger 10 hops
    for _ in range(10):
        hop.handle_trigger(pmt.PMT_T)
    
    print(f"Generated 10 frequencies: {len(freqs)}")
    print(f"First 3: {[f/1e6 for f in freqs[:3]]} MHz")
    
    # Check for uniqueness (unlikely to repeat in 10 hops with 50 channels)
    unique = len(set(freqs))
    print(f"Unique frequencies: {unique}/10")
    
    # Reset seed/counter and check for reproducibility
    hop.handle_set_seed(pmt.from_long(0))
    freqs_reset = []
    def mock_pub_reset(port, msg):
        freqs_reset.append(pmt.to_double(msg))
    hop.message_port_pub = mock_pub_reset
    
    for _ in range(10):
        hop.handle_trigger(pmt.PMT_T)
        
    success = (freqs == freqs_reset)
    print(f"Reproducibility check: {'SUCCESS' if success else 'FAILURE'}")
    return success

def test_tod_hopping():
    print("\n--- [TEST] TOD Sync Hopping ---")
    key = b'\x00' * 32
    num_channels = 50
    center_freq = 915e6
    spacing = 150e3
    dwell_ms = 100
    
    hop1 = tod_hop_generator(key=key, num_channels=num_channels, center_freq=center_freq, channel_spacing=spacing, dwell_ms=dwell_ms)
    hop2 = tod_hop_generator(key=key, num_channels=num_channels, center_freq=center_freq, channel_spacing=spacing, dwell_ms=dwell_ms)
    
    f1 = []; f2 = []
    hop1.message_port_pub = lambda port, msg: f1.append(pmt.to_double(msg))
    hop2.message_port_pub = lambda port, msg: f2.append(pmt.to_double(msg))
    
    # Trigger both at the "same" time
    hop1.handle_trigger(pmt.PMT_T)
    hop2.handle_trigger(pmt.PMT_T)
    
    print(f"Hop 1: {f1[0]/1e6:.3f} MHz")
    print(f"Hop 2: {f2[0]/1e6:.3f} MHz")
    
    success = (f1[0] == f2[0])
    print(f"TOD Synchronization check: {'SUCCESS' if success else 'FAILURE'}")
    
    # Wait for dwell period and check if it changed
    print(f"Waiting {dwell_ms}ms for next epoch...")
    time.sleep(dwell_ms / 1000.0 + 0.1)
    
    f1_next = []
    hop1.message_port_pub = lambda port, msg: f1_next.append(pmt.to_double(msg))
    hop1.handle_trigger(pmt.PMT_T)
    
    changed = (f1[0] != f1_next[0])
    print(f"Epoch transition check: {'SUCCESS' if changed else 'FAILURE'}")
    
    return success and changed

if __name__ == "__main__":
    s1 = test_aes_hopping()
    s2 = test_tod_hopping()
    if s1 and s2:
        print("\nALL HOPPING TESTS PASSED")
        sys.exit(0)
    else:
        print("\nHOPPING TESTS FAILED")
        sys.exit(1)
