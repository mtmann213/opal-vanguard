#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - OFDM Core Math Verification (v1.0)

import numpy as np
import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dsp_helper import OFDMProcessor

def verify_ofdm_math():
    print("--- [TEST] OFDM Core Math Verification ---")
    proc = OFDMProcessor(fft_len=64, cp_len=16)
    
    # Test bits: A simple pattern
    src_bits = [1, 0, 1, 1, 0, 0, 1, 1] * 10 # 80 bits
    print(f"[*] Input Bits: {src_bits[:16]}...")
    
    # 1. Modulate
    samples = proc.modulate(src_bits)
    print(f"[*] Modulation produced {len(samples)} samples.")
    
    # 2. Demodulate (No noise, no shift)
    recovered_bits, conf = proc.demodulate(samples)
    print(f"[*] Recovery produced {len(recovered_bits)} bits.")
    print(f"[*] Recovered Bits: {recovered_bits[:16]}...")
    
    # 3. Compare
    # Note: DF-OFDM might have a small bit-length difference due to symbols/carriers
    # We check if the input pattern exists in the output
    match = False
    for i in range(len(recovered_bits) - len(src_bits) + 1):
        if recovered_bits[i:i+len(src_bits)] == src_bits:
            print(f"\033[92m[SUCCESS] Exact Bit Match Found at offset {i}!\033[0m")
            match = True
            break
            
    if not match:
        print("\033[91m[FAILURE] Bits were corrupted during the OFDM cycle.\033[0m")
        # Diagnostic: How many are different?
        min_len = min(len(src_bits), len(recovered_bits))
        errors = np.sum(np.array(src_bits[:min_len]) != np.array(recovered_bits[:min_len]))
        print(f"[*] Error Rate in direct alignment: {errors}/{min_len} bits")

    return match

if __name__ == "__main__":
    verify_ofdm_math()
