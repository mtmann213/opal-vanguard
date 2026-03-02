#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - RS(31,15) FEC Verification

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from rs_helper import RS3115

def test_rs3115():
    rs = RS3115()
    # 15 symbols of 5 bits (0-31)
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    print(f"Original Data: {data}")
    
    encoded = rs.encode(data)
    print(f"Encoded (31 symbols): {encoded}")
    
    decoded = rs.decode(encoded)
    print(f"Decoded: {decoded}")
    
    if data == decoded:
        print("RS3115 Identity Test: SUCCESS")
        return True
    else:
        print("RS3115 Identity Test: FAILURE")
        return False

if __name__ == "__main__":
    if test_rs3115():
        sys.exit(0)
    else:
        sys.exit(1)
