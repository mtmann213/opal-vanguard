#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - VDF Vector Source Engine (v1.0)

import numpy as np
from gnuradio import gr
import pmt

class vdf_vector_source(gr.sync_block):
    """
    v1.7: A high-performance stream source that emits pilot + data.
    Directly bypasses the PDU-bridge bottleneck.
    """
    def __init__(self):
        gr.sync_block.__init__(self, name="vdf_vector_source", in_sig=None, out_sig=[np.complex64])
        self.data = np.array([], dtype=np.complex64)
        self.ptr = 0
        self.active = False
        
        self.message_port_register_in(pmt.intern("control"))
        self.set_msg_handler(pmt.intern("control"), self.handle_control)

    def handle_control(self, msg):
        """Loads new waveform data into the stream."""
        try:
            samples = pmt.c32vector_elements(msg)
            self.data = np.array(samples, dtype=np.complex64)
            self.ptr = 0
            self.active = True
            print(f"[VDF_SRC] Stream Armed: {len(self.data)} samples loaded.")
        except Exception as e:
            print(f"[VDF_SRC] Load Error: {e}")

    def work(self, input_items, output_items):
        out = output_items[0]
        n = len(out)
        
        if not self.active or self.ptr >= len(self.data):
            self.active = False
            out[:] = 0 # Emit silence when idle
            return n
            
        # Stream the data
        remaining = len(self.data) - self.ptr
        to_send = min(n, remaining)
        out[:to_send] = self.data[self.ptr : self.ptr + to_send]
        
        # Zero-pad if we run out of data in this block
        if to_send < n:
            out[to_send:] = 0
            
        self.ptr += to_send
        return n
