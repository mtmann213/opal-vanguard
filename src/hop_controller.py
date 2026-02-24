#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 michael mann.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#


import numpy
from gnuradio import gr

from gnuradio import gr
import pmt

class lfsr_hop_generator(gr.basic_block):
    """
    Opal Vanguard LFSR Hop Generator
    Emits frequency commands based on LFSR state.
    """
    def __init__(self, seed=1, num_channels=50, center_freq=915e6, channel_spacing=500e3):
        gr.basic_block.__init__(self,
            name="lfsr_hop_generator",
            in_sig=None,
            out_sig=None)
            
        self.num_channels = num_channels
        self.center_freq = center_freq
        self.channel_spacing = channel_spacing
        self.state = seed & 0xFFFF
        
        # Message ports
        self.message_port_register_in(pmt.intern("trigger"))
        self.set_msg_handler(pmt.intern("trigger"), self.handle_trigger)
        self.message_port_register_out(pmt.intern("freq"))

    def handle_trigger(self, msg):
        # Fibonacci LFSR step (16-bit, polynomial x^16 + x^14 + x^13 + x^11 + 1)
        # mask: 0xB400 (bits 15, 13, 12, 10 - 0-indexed)
        feedback = ((self.state >> 15) ^ (self.state >> 13) ^ (self.state >> 12) ^ (self.state >> 10)) & 1
        self.state = ((self.state << 1) & 0xFFFF) | feedback
        
        # Map state to channel index
        channel_idx = self.state % self.num_channels
        freq = self.center_freq + (channel_idx - (self.num_channels // 2)) * self.channel_spacing
        
        # Emit frequency message (PMT double)
        self.message_port_pub(pmt.intern("freq"), pmt.from_double(freq))

    def work(self, input_items, output_items):
        return 0

