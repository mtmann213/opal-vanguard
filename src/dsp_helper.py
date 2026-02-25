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
        
        # Reshape (cols x rows) - because we read columns, they are now rows
        matrix = np.array(list(data)).reshape((cols, self.rows))
        
        # Transpose back to (rows x cols)
        deinterleaved = matrix.T.flatten()
        return bytes(deinterleaved[:original_len].tolist())
