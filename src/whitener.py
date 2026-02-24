#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 michael mann.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#


import numpy
from gnuradio import gr

class whitener(gr.sync_block):
    """
    Opal Vanguard Whitener
    Polynomial: x^7 + x^4 + 1
    """
    def __init__(self, mask=0x48, seed=0x7F):
        gr.sync_block.__init__(self,
            name="whitener",
            in_sig=[numpy.uint8],
            out_sig=[numpy.uint8])
        self.mask = mask
        self.seed = seed
        self.state = seed

    def work(self, input_items, output_items):
        in0 = input_items[0]
        out = output_items[0]
        
        for i in range(len(in0)):
            # Fibonacci LFSR step
            # feedback = bit 7 ^ bit 4 (x^7 + x^4 + 1)
            # wait, x^7 + x^4 + 1 for a 7-bit LFSR.
            # bit 6 is the 7th bit. bit 3 is the 4th bit.
            feedback = ((self.state >> 6) ^ (self.state >> 3)) & 1
            out[i] = in0[i] ^ (self.state & 0xFF) # This is a simple byte-wise XOR if intended, 
                                                 # but usually it's bit-wise.
            # GNU Radio streams are usually bit-wise if it's "packed" or "unpacked".
            # If it's a stream of bits (0/1), it's bit-wise.
            # If it's a stream of bytes, we need to know if we whitener per bit or per byte.
            # Standard whitener for GFSK (like Bluetooth) is bit-wise.
            
            # Let's assume bit-wise whitening for now, as is common for FHSS GFSK.
            # If input is bytes (0 or 1), then:
            out[i] = in0[i] ^ (self.state & 1)
            self.state = ((self.state << 1) & 0x7F) | feedback
            
        return len(output_items[0])
