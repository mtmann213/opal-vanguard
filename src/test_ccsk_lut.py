#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - CCSK LUT Verification (v1.0)

import numpy as np
import time
import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dsp_helper import CCSKProcessor

def test_ccsk_logic():
    print("--- [TEST] CCSK Logic Verification ---")
    proc = CCSKProcessor()
    
    success_count = 0
    for sym in range(32):
        chips = proc.encode_symbol(sym)
        # Test Normal
        recovered, conf = proc.decode_chips(chips)
        if recovered == sym and conf == 1.0:
            # Test Phase Inversion (Link-16 resilient)
            inv_chips = [1 - b for b in chips]
            recovered_inv, conf_inv = proc.decode_chips(inv_chips)
            if recovered_inv == sym and conf_inv == 1.0:
                success_count += 1
            else:
                print(f"FAIL: Phase Inversion failed for symbol {sym}")
        else:
            print(f"FAIL: Normal decode failed for symbol {sym} (Got {recovered}, conf {conf})")
            
    print(f"Result: {success_count}/32 Symbols Verified")
    return success_count == 32

def test_ccsk_performance():
    print("\n--- [TEST] CCSK Performance Benchmarking ---")
    proc = CCSKProcessor()
    chips = proc.encode_symbol(15)
    
    # Warm up
    for _ in range(100): proc.decode_chips(chips)
    
    start = time.time()
    iterations = 10000
    for _ in range(iterations):
        proc.decode_chips(chips)
    end = time.time()
    
    total_time = end - start
    time_per_call = (total_time / iterations) * 1e6 # microseconds
    
    print(f"Iterations: {iterations}")
    print(f"Total Time: {total_time:.4f}s")
    print(f"Average Time: {time_per_call:.2f} us per decode")
    
    # Goal: < 10us per decode for 2.0 Msps fluid operation
    if time_per_call < 10.0:
        print("\033[92m[PASS] Performance target met.\033[0m")
    else:
        print("\033[93m[WARN] Performance below target.\033[0m")

if __name__ == "__main__":
    logic_pass = test_ccsk_logic()
    test_ccsk_performance()
    
    if not logic_pass:
        sys.exit(1)
