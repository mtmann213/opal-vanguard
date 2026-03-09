#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Test script for DSP Helpers (Whitening, Interleaving, DSSS, NRZI)

import os
import sys
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dsp_helper import MatrixInterleaver, DSSSProcessor, NRZIEncoder

def test_whitening():
    # Mock whitening logic from packetizer
    def whiten(data):
        state = 0x7F
        out = []
        for byte in data:
            new_byte = 0
            for i in range(8):
                feedback = ((state >> 6) ^ (state >> 3)) & 1
                bit = (byte >> (7-i)) & 1
                whitened_bit = bit ^ (state & 1)
                new_byte = (new_byte << 1) | whitened_bit
                state = ((state << 1) & 0x7F) | feedback
            out.append(new_byte)
        return bytes(out)

    original = b"Hello World 12345"
    whitened = whiten(original)
    recovered = whiten(whitened)
    
    print(f"Whitening: {'SUCCESS' if original == recovered else 'FAILURE'}")

def test_interleaving():
    interleaver = MatrixInterleaver(rows=8)
    original = b"This is a test of the interleaver logic!"
    interleaved = interleaver.interleave(original)
    recovered = interleaver.deinterleave(interleaved, len(original))
    
    print(f"Interleaving: {'SUCCESS' if original == recovered else 'FAILURE'}")

def test_dsss():
    dsss = DSSSProcessor()
    original_bits = [1, 0, 1, 1, 0, 0, 1, 1]
    chips = dsss.spread(original_bits)
    chips[0] *= -1
    chips[15] *= -1
    recovered_bits = dsss.despread(chips)
    print(f"DSSS: {'SUCCESS' if original_bits == recovered_bits else 'FAILURE'}")

def test_dsss_full_chain():
    dsss = DSSSProcessor()
    original = b"Opal" 
    bits = []
    for b in original:
        for i in range(8): bits.append((b >> (7-i)) & 1)
    chips = dsss.spread(bits)
    demod_bits = [1 if c > 0 else 0 for c in chips]
    recovered_bits = []
    chip_buf = []
    for bit in demod_bits:
        chip = 1 if bit == 1 else -1
        chip_buf.append(chip)
        if len(chip_buf) == dsss.sf:
            recovered_bits.append(dsss.despread(chip_buf)[0])
            chip_buf = []
    recovered_bytes = []
    acc = 0
    for i, bit in enumerate(recovered_bits):
        acc = (acc << 1) | bit
        if (i+1) % 8 == 0:
            recovered_bytes.append(acc)
            acc = 0
    recovered = bytes(recovered_bytes)
    print(f"DSSS Full Chain: {'SUCCESS' if original == recovered else 'FAILURE'}")

def test_nrzi():
    encoder = NRZIEncoder()
    original_bits = [1, 0, 1, 1, 0, 0, 1, 1]
    encoded = encoder.encode(original_bits)
    
    # Normal decode
    decoder1 = NRZIEncoder()
    recovered1 = decoder1.decode(encoded)
    
    # Inverted decode
    inverted = [1 - b for b in encoded]
    decoder2 = NRZIEncoder()
    decoder2.rx_state = 1 # Sync to inverted start
    recovered2 = decoder2.decode(inverted)
    
    print(f"NRZI Normal: {'SUCCESS' if original_bits == recovered1 else 'FAILURE'}")
    print(f"NRZI Inverted: {'SUCCESS' if original_bits == recovered2 else 'FAILURE'}")

if __name__ == "__main__":
    test_whitening()
    test_interleaving()
    test_dsss()
    test_dsss_full_chain()
    test_nrzi()
