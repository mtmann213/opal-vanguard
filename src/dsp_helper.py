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
        ], dtype=np.uint8)
        # Pre-calculate all 32 possible shifts for ultra-fast indexing
        self.shifts = np.array([np.roll(self.base_sequence, -i) for i in range(32)], dtype=np.uint8)
        # Pre-calculate correlation matrix (Bipolar shifts)
        self.base_bipolar_matrix = np.array([np.roll(np.where(self.base_sequence == 1, 1, -1), -i) for i in range(32)], dtype=np.int8)
        # Convert base bipolar for single symbols
        self.base_bipolar = np.where(self.base_sequence == 1, 1, -1).astype(np.int8)

    def encode_symbol(self, symbol):
        """Maps a 5-bit symbol (0-31) to a cyclic shift of the base sequence."""
        return self.shifts[symbol % 32].tolist()

    def vectorized_encode(self, symbols):
        """Encodes a block of 5-bit symbols using pre-calculated matrix indexing."""
        return self.shifts[symbols % 32].flatten().tolist()

    def decode_chips(self, chips):
        """Finds the shift with the highest magnitude correlation using matrix dot product."""
        if len(chips) < 32: return 0, 0.0
        chip_bipolar = np.where(np.array(chips[:32]) == 1, 1, -1).astype(np.int8)
        
        # Single matrix multiplication replaces 32 loops
        correlations = np.abs(np.dot(self.base_bipolar_matrix, chip_bipolar))
        
        best_shift = np.argmax(correlations)
        confidence = correlations[best_shift] / 32.0
        return int(best_shift), float(confidence)

class CSSProcessor:
    """
    Chirp Spread Spectrum (CSS) Processor.
    Uses Linear Frequency Sweeps (Chirps) to represent bits.
    Robust against noise and multipath.
    """
    def __init__(self, sps=128, samp_rate=2000000):
        self.sps = sps
        self.samp_rate = samp_rate
        self.t = np.arange(sps) / samp_rate
        self.bw = samp_rate / 10 # Default bandwidth is 10% of sample rate
        
        # Pre-calculate reference chirps
        # f(t) = f_start + (f_end - f_start) * t / T
        k = self.bw / (sps / samp_rate)
        phase_up = 2 * np.pi * (-self.bw/2 * self.t + 0.5 * k * self.t**2)
        phase_down = 2 * np.pi * (self.bw/2 * self.t - 0.5 * k * self.t**2)
        
        self.up_chirp = np.exp(1j * phase_up).astype(np.complex64)
        self.down_chirp = np.exp(1j * phase_down).astype(np.complex64)

    def modulate(self, bits):
        """Converts bits to a continuous complex baseband chirp signal."""
        out = np.zeros(len(bits) * self.sps, dtype=np.complex64)
        for i, bit in enumerate(bits):
            out[i*self.sps:(i+1)*self.sps] = self.up_chirp if bit == 0 else self.down_chirp
        return out

    def demodulate(self, samples):
        """Recovers bits using conjugate correlation peaks."""
        n_syms = len(samples) // self.sps
        bits = []
        confidences = []
        for i in range(n_syms):
            chunk = samples[i*self.sps:(i+1)*self.sps]
            if len(chunk) < self.sps: break
            # Correlate against both references
            corr_up = np.abs(np.sum(chunk * np.conj(self.up_chirp)))
            corr_down = np.abs(np.sum(chunk * np.conj(self.down_chirp)))
            
            bit = 0 if corr_up > corr_down else 1
            conf = max(corr_up, corr_down) / self.sps
            bits.append(bit)
            confidences.append(conf)
        return bits, confidences

class Scrambler:
    def __init__(self, mask=0x48, seed=0x7F):
        self.mask = mask; self.seed = seed; self.state = seed
        # Pre-calculate a mask for the maximum possible expanded frame size (2048 bytes)
        self.cached_mask = self._generate_mask(2048) 
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
