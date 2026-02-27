#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Advanced DSP Helpers

import numpy as np

class MatrixInterleaver:
    def __init__(self, rows=8):
        self.rows = rows
    def interleave(self, data):
        data_len = len(data)
        cols = (data_len + self.rows - 1) // self.rows
        padded_data = list(data) + [0] * (cols * self.rows - data_len)
        matrix = np.array(padded_data).reshape((self.rows, cols))
        interleaved = matrix.T.flatten()
        return bytes(interleaved.tolist())
    def deinterleave(self, data, original_len):
        data_len = len(data)
        cols = data_len // self.rows
        matrix = np.array(list(data)).reshape((cols, self.rows))
        deinterleaved = matrix.T.flatten()
        return bytes(deinterleaved[:original_len].tolist())

class DSSSProcessor:
    def __init__(self, chipping_code=[1, -1]):
        self.code = np.array(chipping_code)
        self.sf = len(self.code)
    def spread(self, bits):
        chips = []
        for bit in bits:
            val = 1 if bit == 1 else -1
            chips.extend((val * self.code).tolist())
        return chips
    def despread(self, chips):
        bits = []
        for i in range(0, len(chips), self.sf):
            chunk = np.array(chips[i:i+self.sf]); correlation = np.sum(chunk * self.code)
            bits.append(1 if correlation > 0 else 0)
        return bits

class NRZIEncoder:
    def __init__(self):
        self.tx_state = 0
        self.rx_state = 0
    def reset(self):
        self.tx_state = 0
        self.rx_state = 0
    def encode(self, bits):
        encoded = []; state = self.tx_state
        for bit in bits:
            if bit == 1: state = 1 - state
            encoded.append(state)
        self.tx_state = state
        return encoded
    def decode(self, bits):
        decoded = []; prev_state = self.rx_state
        for state in bits:
            decoded.append(1 if state != prev_state else 0)
            prev_state = state
        self.rx_state = prev_state
        return decoded

class ManchesterEncoder:
    def reset(self):
        pass
    def encode(self, bits):
        out = []
        for b in bits:
            if b == 1: out.extend([1, 0])
            else: out.extend([0, 1])
        return out
    def decode(self, bits):
        out = []
        for i in range(0, len(bits), 2):
            pair = bits[i:i+2]
            if len(pair) < 2: break
            out.append(1 if pair == [1, 0] else 0)
        return out

class Scrambler:
    def __init__(self, mask=0x48, seed=0x7F):
        self.mask = mask
        self.seed = seed
    def process(self, data):
        state = self.seed
        out = []
        for byte in data:
            new_byte = 0
            for i in range(8):
                feedback = 0
                for bit_pos in range(7):
                    if (self.mask >> bit_pos) & 1: feedback ^= (state >> bit_pos) & 1
                bit = (byte >> (7-i)) & 1
                new_byte = (new_byte << 1) | (bit ^ (state & 1))
                state = ((state << 1) & 0x7F) | (feedback & 1)
            out.append(new_byte)
        return bytes(out)
