#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Test script for RS(15,11) Error Correction

from rs_helper import RS1511

def test_rs():
    rs = RS1511()
    
    # 1. Original Data (11 nibbles)
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    print(f"Original:  {data}")
    
    # 2. Encode
    encoded = rs.encode(data)
    print(f"Encoded:   {encoded}")
    
    # 3. Inject Errors (up to 2 nibbles)
    corrupted = list(encoded)
    corrupted[0] ^= 0x05 # Error 1 at pos 0
    corrupted[5] ^= 0x0A # Error 2 at pos 5
    print(f"Corrupted: {corrupted}")
    
    # 4. Decode (Correct)
    decoded = rs.decode(corrupted)
    print(f"Decoded:   {decoded}")
    
    if list(data) == list(decoded):
        print("\nSUCCESS: Errors corrected perfectly!")
    else:
        print("\nFAILURE: Errors not corrected.")

if __name__ == "__main__":
    test_rs()
