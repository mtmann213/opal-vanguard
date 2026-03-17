#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Advanced DSP Helpers (v16.0.32 Downscaled)

import numpy as np

class MatrixInterleaver:
    def __init__(self, rows=8):
        self.rows = rows
    def interleave(self, data, *args):
        arr = np.frombuffer(data, dtype=np.uint8)
        data_len = len(arr)
        cols = (data_len + self.rows - 1) // self.rows
        if data_len < (cols * self.rows):
            arr = np.append(arr, np.zeros((cols * self.rows) - data_len, dtype=np.uint8))
        matrix = arr.reshape((self.rows, cols))
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

class NRZIEncoder:
    def __init__(self):
        self.tx_state = 0; self.rx_state = 0
    def reset(self):
        self.tx_state = 0; self.rx_state = 0
    def encode(self, bits):
        bits_arr = np.array(bits, dtype=np.uint8)
        res = np.bitwise_xor.accumulate(np.insert(bits_arr, 0, self.tx_state))
        self.tx_state = int(res[-1])
        return res[1:].tolist()
    def decode(self, bits):
        bits_arr = np.array(bits, dtype=np.uint8)
        prev = np.roll(bits_arr, 1); prev[0] = self.rx_state
        decoded = np.bitwise_xor(bits_arr, prev)
        self.rx_state = int(bits_arr[-1])
        return decoded.tolist()

class CCSKProcessor:
    def __init__(self):
        self.base_sequence = np.array([
            0, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0, 1, 0, 0, 1,
            0, 0, 0, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 1, 0, 0
        ])
        self.lut_matrix = np.zeros((32, 32), dtype=np.int8)
        for i in range(32):
            self.lut_matrix[i] = np.where(np.roll(self.base_sequence, -i) == 1, 1, -1)
    def encode_symbol(self, symbol):
        shift = symbol % 32
        return np.roll(self.base_sequence, -shift).tolist()
    def decode_chips(self, chips):
        if len(chips) < 32: return 0, 0.0
        chip_bipolar = np.where(np.array(chips[:32]) == 1, 1, -1)
        correlations = np.abs(np.dot(self.lut_matrix, chip_bipolar))
        best_shift = np.argmax(correlations)
        confidence = correlations[best_shift] / 32.0
        return best_shift, confidence

class Scrambler:
    def __init__(self, mask=0x48, seed=0x7F):
        self.mask = mask; self.seed = seed; self.state = seed
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
        return np.packbits(np.array(mask_bits, dtype=np.uint8))
    def process(self, data):
        arr = np.frombuffer(data, dtype=np.uint8)
        scrambled = arr ^ self.cached_mask[:len(arr)]
        return scrambled.tobytes()

class OFDMProcessor:
    """
    v16.0.32: Downscaled 32-point OFDM Engine for stability testing.
    """
    def __init__(self, fft_len=32, cp_len=8):
        self.fft_len = fft_len
        self.cp_len = cp_len
        # Contiguous carriers 2 to 14 (13 carriers total)
        self.data_idx = np.arange(2, 15) 
        self.n_data = len(self.data_idx)
        self.zc_pilot = self.generate_zc_pulse(32)

    def generate_zc_pulse(self, length=32, u=1):
        """Generates a Zadoff-Chu sequence for robust timing sync."""
        n = np.arange(length)
        return np.exp(-1j * np.pi * u * n * (n + 1) / length).astype(np.complex64)

    def modulate(self, bits):
        """Vectorized DF-OFDM Modulation."""
        bits_arr = np.array(bits, dtype=np.uint8)
        n_bits_per_symbol = self.n_data - 1
        n_symbols = (len(bits_arr) + (n_bits_per_symbol - 1)) // n_bits_per_symbol
        
        data_bits = np.zeros(n_symbols * n_bits_per_symbol)
        data_bits[:len(bits_arr)] = np.where(bits_arr == 1, -1.0, 1.0)
        data_matrix = data_bits.reshape(n_symbols, n_bits_per_symbol)
        
        df_symbols = np.ones((n_symbols, self.n_data), dtype=np.complex64)
        df_symbols[:, 1:] = np.cumprod(data_matrix, axis=1)
        
        grid = np.zeros((n_symbols, self.fft_len), dtype=np.complex64)
        grid[:, self.data_idx] = df_symbols
        
        time_domain = np.fft.ifft(np.fft.ifftshift(grid, axes=1), axis=1)
        cp = time_domain[:, -self.cp_len:]
        return np.hstack([cp, time_domain]).flatten()

    def demodulate(self, samples):
        """Vectorized DF-OFDM Demodulation."""
        samples_arr = np.array(samples, dtype=np.complex64)
        n_full = self.fft_len + self.cp_len
        n_symbols = len(samples_arr) // n_full
        matrix = samples_arr[:n_symbols * n_full].reshape(-1, n_full)
        grid = np.fft.fftshift(np.fft.fft(matrix[:, self.cp_len:], axis=1), axes=1)
        data_grid = grid[:, self.data_idx]
        diffs = data_grid[:, 1:] * np.conj(data_grid[:, :-1])
        bits = (np.real(diffs) < 0).astype(np.uint8).flatten()
        return bits.tolist(), 1.0
