#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - TOD (Time-of-Day) Synced Hop Generator

import numpy as np
from gnuradio import gr
import pmt
import time
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class tod_hop_generator(gr.basic_block):
    def __init__(self, key=b'\x00'*32, num_channels=50, center_freq=915e6, channel_spacing=150e3, dwell_ms=200, lookahead_ms=0):
        gr.basic_block.__init__(self, name="tod_hop_generator", in_sig=None, out_sig=None)
            
        self.num_channels = num_channels
        self.center_freq = center_freq
        self.channel_spacing = channel_spacing
        self.key = key
        self.dwell_sec = dwell_ms / 1000.0
        self.lookahead_sec = lookahead_ms / 1000.0
        
        self.backend = default_backend()
        
        # Message ports
        self.message_port_register_in(pmt.intern("trigger"))
        self.set_msg_handler(pmt.intern("trigger"), self.handle_trigger)
        
        self.message_port_register_out(pmt.intern("freq"))

    def handle_trigger(self, msg):
        """Calculates frequency based on absolute system time."""
        # 1. Get current time + lookahead
        now = time.time() + self.lookahead_sec
        
        # 2. Determine the discrete 'Epoch' (how many dwell intervals since 1970)
        epoch = int(now / self.dwell_sec)
        
        # 3. Generate AES-CTR keystream for this specific epoch
        nonce = struct.pack(">QQ", 0, epoch)
        cipher = Cipher(algorithms.AES(self.key), modes.ECB(), backend=self.backend)
        encryptor = cipher.encryptor()
        keystream = encryptor.update(nonce) + encryptor.finalize()
        
        # 4. Map to channel
        rand_val = struct.unpack(">I", keystream[:4])[0]
        channel_idx = rand_val % self.num_channels
        freq = self.center_freq + (channel_idx - (self.num_channels // 2)) * self.channel_spacing
        
        print(f"[TOD Hop] Epoch: {epoch} | Chan: {channel_idx} | Freq: {freq/1e6:.3f} MHz")
        self.message_port_pub(pmt.intern("freq"), pmt.from_double(freq))

    def work(self, input_items, output_items):
        return 0
