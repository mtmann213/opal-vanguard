#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Advanced DSP Helpers

import numpy as np

class MatrixInterleaver:
    def __init__(self, rows=8):
        self.rows = rows
    def interleave(self, data, *args):
        # Convert to numpy directly from buffer
        arr = np.frombuffer(data, dtype=np.uint8)
        data_len = len(arr)
        cols = (data_len + self.rows - 1) // self.rows
        # Pad with zeros if necessary
        if data_len < (cols * self.rows):
            arr = np.append(arr, np.zeros((cols * self.rows) - data_len, dtype=np.uint8))
        matrix = arr.reshape((self.rows, cols))
        # Transpose and flatten (Column-major to Row-major swap)
        interleaved = matrix.T.flatten()
        return interleaved.tobytes()
    def deinterleave(self, data, *args):
        arr = np.frombuffer(data, dtype=np.uint8)
        data_len = len(arr)
        original_len = args[0] if args else data_len
        cols = (data_len + self.rows - 1) // self.rows
        matrix = arr.reshape((cols, self.rows))
        deinterleaved = matrix.T.flatten()
        return deinterleaved[:original_len].tobytes()

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
        self.tx_state = 0; self.rx_state = 0
    def reset(self):
        self.tx_state = 0; self.rx_state = 0
    def encode(self, bits):
        # Use NumPy to calculate transitions (1 means flip state)
        bits_arr = np.array(bits, dtype=np.uint8)
        # Cumulative XOR effectively implements the NRZI state machine
        # We must include the initial state in the calculation
        # np.bitwise_xor.accumulate is the vectorized equivalent of our loop
        res = np.bitwise_xor.accumulate(np.insert(bits_arr, 0, self.tx_state))
        self.tx_state = int(res[-1])
        return res[1:].tolist()
    def decode(self, bits):
        bits_arr = np.array(bits, dtype=np.uint8)
        # XOR with previous bit to find transitions
        prev = np.roll(bits_arr, 1); prev[0] = self.rx_state
        decoded = np.bitwise_xor(bits_arr, prev)
        self.rx_state = int(bits_arr[-1])
        return decoded.tolist()

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
        self.mask = mask; self.seed = seed; self.state = seed
        # Pre-calculate a mask for the maximum possible frame size (1024 bytes)
        self.cached_mask = self._generate_mask(1024) 
    def reset(self):
        self.state = self.seed
    def _generate_mask(self, n_bytes):
        mask_bits = []
        state = self.seed
        for _ in range(n_bytes * 8):
            feedback = 0
            for bit_pos in range(7):
                if (self.mask >> bit_pos) & 1: feedback ^= (state >> bit_pos) & 1
            mask_bits.append(state & 1)
            state = ((state << 1) & 0x7F) | (feedback & 1)
        # Pack bits into uint8 bytes for easy XORing
        return np.packbits(np.array(mask_bits, dtype=np.uint8))
    def process(self, data):
        # Extremely fast vectorized XOR
        arr = np.frombuffer(data, dtype=np.uint8)
        scrambled = arr ^ self.cached_mask[:len(arr)]
        return scrambled.tobytes()
