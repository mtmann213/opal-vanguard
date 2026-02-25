#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class RS1511:
    def __init__(self):
        # GF(16) tables (Polynomial: x^4 + x + 1)
        self.exp = [1, 2, 4, 8, 3, 6, 12, 11, 5, 10, 7, 14, 15, 13, 9] * 3
        self.log = [0] * 16
        for i in range(15): self.log[self.exp[i]] = i
        # Generator: x^4 + 13x^3 + 12x^2 + 8x + 10
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
        
        # Brute force 1-symbol error
        for i in range(15):
            for val in range(1, 16):
                corrupted = list(msg_in)
                corrupted[i] ^= val
                if self.is_valid(corrupted):
                    return list(corrupted[:11])
        
        # Brute force 2-symbol error (still fast for 15 symbols)
        for i in range(15):
            for j in range(i + 1, 15):
                for v1 in range(1, 16):
                    for v2 in range(1, 16):
                        corrupted = list(msg_in)
                        corrupted[i] ^= v1
                        corrupted[j] ^= v2
                        if self.is_valid(corrupted):
                            return list(corrupted[:11])
        
        return list(msg_in[:11]) # Could not correct
