#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import numpy as np
from gnuradio import gr
import pmt

class msg_to_rotator(gr.sync_block):
    """
    Translates a frequency message into a Phase Increment for a Rotator block.
    Uses a lazy lookup of the rotator block within the parent top_block.
    """
    def __init__(self, parent=None, rotator_id="rot_tx", center_freq=915e6, samp_rate=2e6, invert=False):
        gr.sync_block.__init__(self, name="Message to Rotator", in_sig=None, out_sig=None)
        self.parent = parent
        self.rotator_id = rotator_id
        self.center_freq = center_freq
        self.samp_rate = samp_rate
        self.invert = invert
        
        self.message_port_register_in(pmt.intern("msg"))
        self.set_msg_handler(pmt.intern("msg"), self.handle_msg)

    def handle_msg(self, msg):
        try:
            freq = pmt.to_double(msg)
            offset = freq - self.center_freq
            phase_inc = 2 * np.pi * offset / self.samp_rate
            if self.invert:
                phase_inc = -phase_inc
                
            if self.parent:
                rot_block = getattr(self.parent, self.rotator_id, None)
                if rot_block:
                    rot_block.set_phase_inc(phase_inc)
        except Exception as e:
            print(f"MsgToRotator Error: {e}")

    def work(self, input_items, output_items):
        return 0
