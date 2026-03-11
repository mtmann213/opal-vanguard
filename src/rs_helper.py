#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Reed-Solomon FEC Helpers (GF(16))
# Optimized for high-speed tactical links.

class RS1511:
    """Standard Reed-Solomon (15, 11) over GF(16)."""
    def __init__(self):
        self.K, self.N = 11, 15
        # GF(16) tables (Polynomial: x^4 + x + 1)
        self.exp = [1, 2, 4, 8, 3, 6, 12, 11, 5, 10, 7, 14, 15, 13, 9] * 3
        self.log = [0] * 16
        for i in range(15): self.log[self.exp[i]] = i
        self.gen = [1, 13, 12, 8, 10]

    def gf_mul(self, a, b):
        if a == 0 or b == 0: return 0
        return self.exp[self.log[a] + self.log[b]]

    def encode(self, data):
        msg = list(data) + [0] * 4
        for i in range(11):
            feedback = msg[i]
            if feedback != 0:
                for j in range(1, 5):
                    msg[i+j] ^= self.gf_mul(self.gen[j], feedback)
        return list(data) + msg[11:]

    def is_valid(self, msg):
        rem = list(msg)
        for i in range(11):
            feedback = rem[i]
            if feedback != 0:
                for j in range(1, 5):
                    rem[i+j] ^= self.gf_mul(self.gen[j], feedback)
        return not any(rem[11:])

    def decode(self, msg_in, max_errors=1):
        if self.is_valid(msg_in): return list(msg_in[:11]), 0
        
        # Optimized 1-symbol error correction (Brute Force for GF16)
        if max_errors >= 1:
            corrupted = list(msg_in)
            for i in range(15):
                orig = corrupted[i]
                for val in range(1, 16):
                    corrupted[i] = orig ^ val
                    if self.is_valid(corrupted): return list(corrupted[:11]), 1
                corrupted[i] = orig # Restore
        
        # 2-symbol correction is too slow for real-time SDR
        if max_errors >= 2:
            for i in range(14):
                for j in range(i+1, 15):
                    for val1 in range(1, 16):
                        for val2 in range(1, 16):
                            corrupted = list(msg_in)
                            corrupted[i] ^= val1
                            corrupted[j] ^= val2
                            if self.is_valid(corrupted): return list(corrupted[:11]), 2
                        
        return list(msg_in[:11]), 0
