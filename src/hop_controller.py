#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - LFSR Hop Generator (with Dynamic Seed)

from gnuradio import gr
import pmt


class lfsr_hop_generator(gr.basic_block):
    def __init__(
        self, seed=1, num_channels=50, center_freq=915e6, channel_spacing=500e3
    ):
        gr.basic_block.__init__(
            self, name="lfsr_hop_generator", in_sig=None, out_sig=None
        )

        self.num_channels = num_channels
        self.center_freq = center_freq
        self.channel_spacing = channel_spacing
        # Guard against zero seed (LFSR lockup)
        self.state = (seed & 0xFFFF) if (seed & 0xFFFF) != 0 else 0xACE

        # Message ports
        self.message_port_register_in(pmt.intern("trigger"))
        self.set_msg_handler(pmt.intern("trigger"), self.handle_trigger)

        self.message_port_register_in(pmt.intern("set_seed"))
        self.set_msg_handler(pmt.intern("set_seed"), self.handle_set_seed)

        self.message_port_register_out(pmt.intern("freq"))

    def handle_set_seed(self, msg):
        new_seed = pmt.to_long(msg)
        # Guard against zero seed
        self.state = (new_seed & 0xFFFF) if (new_seed & 0xFFFF) != 0 else 0xACE
        print(f"[HopCtrl] Seed synced to: 0x{self.state:04X}")

    def handle_trigger(self, msg):
        # 16-bit Fibonacci LFSR step (primitive polynomial x^16 + x^14 + x^13 + x^11 + 1)
        feedback = (
            (self.state >> 15)
            ^ (self.state >> 13)
            ^ (self.state >> 12)
            ^ (self.state >> 10)
        ) & 1
        self.state = ((self.state << 1) & 0xFFFF) | feedback

        channel_idx = self.state % self.num_channels
        freq = (
            self.center_freq
            + (channel_idx - (self.num_channels // 2)) * self.channel_spacing
        )

        out_dict = pmt.make_dict()
        out_dict = pmt.dict_add(out_dict, pmt.intern("freq"), pmt.from_double(freq))
        out_dict = pmt.dict_add(out_dict, pmt.intern("time"), pmt.from_double(0.0))
        self.message_port_pub(pmt.intern("freq"), out_dict)

    def work(self, input_items, output_items):
        return 0
