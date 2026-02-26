#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - DSP Helpers (Interleaving & Advanced Logic)

import numpy as np

class MatrixInterleaver:
    """
    A simple Matrix Interleaver to combat burst errors.
    Writes data in rows and reads it out in columns.
    """
    def __init__(self, rows=8):
        self.rows = rows

    def interleave(self, data):
        """
        Shuffles data using a matrix of specified rows.
        Padding is added if the data doesn't perfectly fit.
        """
        data_len = len(data)
        cols = (data_len + self.rows - 1) // self.rows
        
        # Pad with zeros
        padded_data = list(data) + [0] * (cols * self.rows - data_len)
        
        # Reshape to matrix (rows x cols)
        matrix = np.array(padded_data).reshape((self.rows, cols))
        
        # Read out by columns (Transposed)
        interleaved = matrix.T.flatten()
        return bytes(interleaved.tolist())

    def deinterleave(self, data, original_len):
        """
        Reverses the interleaving process.
        original_len is required to strip padding.
        """
        data_len = len(data)
        cols = data_len // self.rows
        
        # Reshape (cols x rows)
        matrix = np.array(list(data)).reshape((cols, self.rows))
        
        # Transpose back to (rows x cols)
        deinterleaved = matrix.T.flatten()
        return bytes(deinterleaved[:original_len].tolist())

class DSSSProcessor:
    """
    Direct Sequence Spread Spectrum Processor.
    Spreads each bit into a sequence of 'chips'.
    """
    def __init__(self, chipping_code=[1, 1, 1, -1, -1, -1, 1, -1, -1, 1, -1]):
        self.code = np.array(chipping_code)
        self.sf = len(self.code)

    def spread(self, bits):
        """
        Spreads a bitstream (0/1) into chips (-1/1).
        Input is list of bits, output is list of chips.
        """
        chips = []
        for bit in bits:
            val = 1 if bit == 1 else -1
            chips.extend((val * self.code).tolist())
        return chips

    def despread(self, chips):
        """
        Correlates incoming chips with the code to recover bits.
        Input is list of chips, output is list of bits (0/1).
        """
        bits = []
        for i in range(0, len(chips), self.sf):
            chunk = np.array(chips[i:i+self.sf])
            if len(chunk) < self.sf: break
            correlation = np.sum(chunk * self.code)
            bits.append(1 if correlation > 0 else 0)
        return bits

class NRZIEncoder:
    """
    Non-Return-to-Zero Inverted (NRZ-I) Encoder/Decoder.
    1 = Transition, 0 = No Transition.
    Provides immunity to bit inversion (180-degree phase/FM polarity).
    """
    def __init__(self):
        self.tx_state = 0
        self.rx_state = 0

    def encode(self, bits):
        """Encodes bits to NRZ-I."""
        encoded = []
        state = self.tx_state
        for bit in bits:
            if bit == 1:
                state = 1 - state
            encoded.append(state)
        self.tx_state = state
        return encoded

    def decode(self, bits):
        """Decodes NRZ-I bits back to original."""
        decoded = []
        prev_state = self.rx_state
        for state in bits:
            if state != prev_state:
                decoded.append(1)
            else:
                decoded.append(0)
            prev_state = state
        self.rx_state = prev_state
        return decoded
