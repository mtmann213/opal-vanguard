#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Minimal Reed-Solomon (15, 11) Implementation over GF(16)
# Polynomial: x^4 + x + 1

import numpy as np

class RS1511:
    def __init__(self):
        # GF(16) tables
        self.exp = [1, 2, 4, 8, 3, 6, 12, 11, 5, 10, 7, 14, 15, 13, 9, 1]
        self.log = [0] * 16
        for i in range(15):
            self.log[self.exp[i]] = i
            
        # Generator polynomial for RS(15, 11) - 4 parity symbols
        # g(x) = (x+a^1)(x+a^2)(x+a^3)(x+a^4)
        # For simplicity, we'll use a precomputed generator for 4 parity symbols.
        # Coefficients in alpha power: [0, 13, 12, 8, 10] -> [1, 13, 12, 5, 7] in decimal
        self.gen = [1, 13, 12, 5, 7]

    def gf_mul(self, a, b):
        if a == 0 or b == 0: return 0
        return self.exp[(self.log[a] + self.log[b]) % 15]

    def encode(self, data_in):
        """Encodes 11 nibbles (4-bit) into 15 nibbles."""
        # data_in should be length 11, values 0-15
        msg = list(data_in) + [0] * 4
        for i in range(11):
            feedback = msg[i]
            if feedback != 0:
                for j in range(1, 5):
                    msg[i + j] ^= self.gf_mul(self.gen[j], feedback)
        return list(data_in) + msg[11:]

    def decode(self, msg_in):
        """Very basic 'decoder' that just returns data (no correction for now).
        A real decoder would use syndromes + Berlekamp-Massey.
        For a demo, we'll just strip parity.
        """
        return msg_in[:11]

# Since our system works on bytes, we'll need to pack/unpack bytes to nibbles.
def bytes_to_nibbles(data):
    nibbles = []
    for b in data:
        nibbles.append((b >> 4) & 0x0F)
        nibbles.append(b & 0x0F)
    return nibbles

def nibbles_to_bytes(nibbles):
    bytes_out = []
    for i in range(0, len(nibbles), 2):
        b = (nibbles[i] << 4) | nibbles[i+1]
        bytes_out.append(b)
    return bytes(bytes_out)
