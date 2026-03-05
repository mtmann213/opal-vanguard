#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Standalone test for RS3115

from rs_helper import RS3115

def test_rs3115():
    rs = RS3115()
    
    # 1. 15 symbols (5 bits each)
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    print(f"Original:  {data}")
    
    # 2. Encode
    encoded = rs.encode(data)
    print(f"Encoded:   {encoded}")
    
    # 3. Verify
    if not rs.is_valid(encoded):
        print("FAILURE: Encoded message is NOT valid!")
        return
    
    # 4. Decode
    decoded = rs.decode(encoded)
    print(f"Decoded:   {decoded}")
    
    if data == decoded:
        print("SUCCESS: Perfect recovery.")
    else:
        print("FAILURE: Recovery failed.")

if __name__ == "__main__":
    test_rs3115()
