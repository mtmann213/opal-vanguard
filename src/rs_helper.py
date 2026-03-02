#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Reed-Solomon FEC Helpers (GF(16) and GF(32))

class RS1511:
    """Standard Reed-Solomon (15, 11) over GF(16)."""
    def __init__(self):
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
        return max(rem[11:]) == 0

    def decode(self, msg_in):
        if self.is_valid(msg_in): return list(msg_in[:11])
        # Simple 1-symbol error correction (Brute Force for GF16)
        for i in range(15):
            for val in range(1, 16):
                corrupted = list(msg_in)
                corrupted[i] ^= val
                if self.is_valid(corrupted): return list(corrupted[:11])
        
        # Simple 2-symbol error correction
        for i in range(14):
            for j in range(i+1, 15):
                for val1 in range(1, 16):
                    for val2 in range(1, 16):
                        corrupted = list(msg_in)
                        corrupted[i] ^= val1
                        corrupted[j] ^= val2
                        if self.is_valid(corrupted): return list(corrupted[:11])
                        
        return list(msg_in[:11])

class RS3115:
    """Link 16 Standard Reed-Solomon (31, 15) over GF(32)."""
    def __init__(self):
        # GF(32) tables (Polynomial: x^5 + x^2 + 1)
        self.exp = [1, 2, 4, 8, 16, 5, 10, 20, 13, 26, 17, 7, 14, 28, 29, 31, 27, 19, 3, 6, 12, 24, 21, 15, 30, 25, 23, 11, 22, 18, 1] * 3
        self.log = [0] * 32
        for i in range(31): self.log[self.exp[i]] = i
        
        # Generator for 16 parity symbols
        # Real Link 16 uses a specific systematic generator. 
        # We'll use this consistent LFSR generator for our emulation.
        self.gen = [1, 2, 4, 8, 16, 5, 10, 20, 13, 26, 17, 7, 14, 28, 29, 31, 27]

    def gf_mul(self, a, b):
        if a == 0 or b == 0: return 0
        return self.exp[self.log[a] + self.log[b]]

    def encode(self, data):
        msg = list(data) + [0] * 16
        for i in range(15):
            feedback = msg[i]
            if feedback != 0:
                for j in range(1, 17):
                    msg[i+j] ^= self.gf_mul(self.gen[j], feedback)
        return list(data) + msg[15:]

    def is_valid(self, msg):
        rem = list(msg)
        for i in range(15):
            feedback = rem[i]
            if feedback != 0:
                for j in range(1, 17):
                    rem[i+j] ^= self.gf_mul(self.gen[j], feedback)
        return max(rem[15:]) == 0

    def decode(self, msg_in):
        """Attempts to correct errors using brute-force for up to 1 symbol."""
        if self.is_valid(msg_in): return list(msg_in[:15])
        
        # RS(31,15) can fix 8 symbols, but brute force is O(N^T).
        # We'll implement a 1-symbol "Quick Repair" to stabilize the link for now.
        for i in range(31):
            for val in range(1, 32):
                corrupted = list(msg_in)
                corrupted[i] ^= val
                if self.is_valid(corrupted):
                    return list(corrupted[:15])
        
        return list(msg_in[:15])
