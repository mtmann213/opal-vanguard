#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Advanced DSP Helpers

import numpy as np

class MatrixInterleaver:
    def __init__(self, rows=8):
        self.rows = rows
    def interleave(self, data, *args):
        data_len = len(data)
        cols = (data_len + self.rows - 1) // self.rows
        padded_data = list(data) + [0] * (cols * self.rows - data_len)
        matrix = np.array(padded_data).reshape((self.rows, cols))
        interleaved = matrix.T.flatten()
        return bytes(interleaved.tolist())
    def deinterleave(self, data, *args):
        data_len = len(data)
        original_len = args[0] if args else data_len
        cols = (data_len + self.rows - 1) // self.rows
        matrix = np.array(list(data)).reshape((cols, self.rows))
        deinterleaved = matrix.T.flatten()
        return bytes(deinterleaved[:original_len].tolist())

class DSSSProcessor:
    def __init__(self, sf=31, chipping_code=None):
        if chipping_code is None or len(chipping_code) == 0:
            # Default to Barker 11 if nothing provided
            self.code = np.array([1, 1, 1, -1, -1, -1, 1, -1, -1, 1, -1])
        else:
            self.code = np.array(chipping_code)
        self.sf = len(self.code)
    def spread(self, bits):
        chips = []
        for bit in bits:
            val = 1 if bit == 1 else -1
            chips.extend((val * self.code).tolist())
        return chips
    def despread(self, chips):
        chunk = np.array(chips[:self.sf])
        correlation = np.sum(chunk * self.code)
        recovered_bit = 1 if correlation > 0 else 0
        return recovered_bit, correlation

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

class CCSKProcessor:
    def __init__(self):
        # Standard Link-16 32-chip base sequence
        self.base_sequence = np.array([
            0, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0, 1, 0, 0, 1,
            0, 0, 0, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 1, 0, 0
        ])
        # Convert to bipolar (+1, -1) for correlation
        self.base_bipolar = np.where(self.base_sequence == 1, 1, -1)

    def encode_symbol(self, symbol):
        """Maps a 5-bit symbol (0-31) to a cyclic shift of the base sequence."""
        shift = symbol % 32
        return np.roll(self.base_sequence, -shift).tolist()

    def decode_chips(self, chips):
        """Finds the shift with the highest magnitude correlation to recover the 5-bit symbol."""
        if len(chips) < 32: return 0, 0.0
        chip_bipolar = np.where(np.array(chips[:32]) == 1, 1, -1)
        
        correlations = []
        for shift in range(32):
            ref = np.roll(self.base_bipolar, -shift)
            # Use absolute sum to handle phase inversions natively
            correlations.append(abs(np.sum(chip_bipolar * ref)))
        
        best_shift = np.argmax(correlations)
        confidence = correlations[best_shift] / 32.0
        return best_shift, confidence

class Scrambler:
    def __init__(self, mask=0x48, seed=0x7F):
        self.mask = mask
        self.seed = seed
        self.state = seed
    def reset(self):
        self.state = self.seed
    def process(self, data):
        out = []
        for byte in data:
            new_byte = 0
            for i in range(8):
                feedback = 0
                for bit_pos in range(7):
                    if (self.mask >> bit_pos) & 1: feedback ^= (self.state >> bit_pos) & 1
                bit = (byte >> (7-i)) & 1
                new_byte = (new_byte << 1) | (bit ^ (self.state & 1))
                self.state = ((self.state << 1) & 0x7F) | (feedback & 1)
            out.append(new_byte)
        return bytes(out)
