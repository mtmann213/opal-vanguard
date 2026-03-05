#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - AES-CTR Hop Generator (TRANSEC with AFH)

import numpy as np
from gnuradio import gr
import pmt
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class aes_hop_generator(gr.basic_block):
    def __init__(self, key=b'\x00'*32, num_channels=50, center_freq=915e6, channel_spacing=150e3):
        gr.basic_block.__init__(self, name="aes_hop_generator", in_sig=None, out_sig=None)
            
        self.num_channels = num_channels
        self.center_freq = center_freq
        self.channel_spacing = channel_spacing
        self.key = key
        self.counter = 0
        self.blacklist = []
        
        # Cipher Setup
        self.backend = default_backend()
        
        # Message ports
        self.message_port_register_in(pmt.intern("trigger"))
        self.set_msg_handler(pmt.intern("trigger"), self.handle_trigger)
        
        self.message_port_register_in(pmt.intern("set_seed")) # Seed acts as initial counter
        self.set_msg_handler(pmt.intern("set_seed"), self.handle_set_seed)
        
        self.message_port_register_in(pmt.intern("blacklist"))
        self.set_msg_handler(pmt.intern("blacklist"), self.handle_blacklist)
        
        self.message_port_register_out(pmt.intern("freq"))

    def handle_set_seed(self, msg):
        new_seed = pmt.to_long(msg)
        self.counter = new_seed
        print(f"[HopAES] Counter synced to: {self.counter}")

    def handle_blacklist(self, msg):
        if pmt.is_vector_obj(msg):
            self.blacklist = list(pmt.u8vector_elements(msg))
            print(f"[AFH-AES] Blacklist updated: {self.blacklist}")

    def handle_trigger(self, msg):
        nonce = struct.pack(">QQ", 0, self.counter)
        cipher = Cipher(algorithms.AES(self.key), modes.ECB(), backend=self.backend)
        encryptor = cipher.encryptor()
        keystream = encryptor.update(nonce) + encryptor.finalize()
        
        rand_val = struct.unpack(">I", keystream[:4])[0]
        raw_idx = rand_val % self.num_channels
        
        # AFH Remapping
        final_idx = raw_idx
        if self.blacklist and final_idx in self.blacklist:
            for i in range(1, self.num_channels):
                candidate = (raw_idx + i) % self.num_channels
                if candidate not in self.blacklist:
                    final_idx = candidate
                    break
        
        freq = self.center_freq + (final_idx - (self.num_channels // 2)) * self.channel_spacing
        
        if final_idx != raw_idx:
            print(f"\033[96m[AFH-AES] EVADED {raw_idx} -> Moved to {final_idx}\033[0m")
            
        self.message_port_pub(pmt.intern("freq"), pmt.from_double(freq))
        self.counter = (self.counter + 1) & 0xFFFFFFFFFFFFFFFF

    def work(self, input_items, output_items):
        return 0
