#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - TOD (Time-of-Day) Synced Hop Generator (AFH Capable)

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
        self.blacklist = [] # List of channel indices to avoid
        
        # Message ports
        self.message_port_register_in(pmt.intern("trigger"))
        self.set_msg_handler(pmt.intern("trigger"), self.handle_trigger)
        
        self.message_port_register_in(pmt.intern("blacklist"))
        self.set_msg_handler(pmt.intern("blacklist"), self.handle_blacklist)
        
        self.message_port_register_out(pmt.intern("freq"))

    def handle_blacklist(self, msg):
        """Expects a list of integers via PMT vector or python-converted object."""
        try:
            if pmt.is_u8vector(msg):
                self.blacklist = list(pmt.u8vector_elements(msg))
            else:
                # Handle generic python objects passed through PMT
                new_list = pmt.to_python(msg)
                if isinstance(new_list, list):
                    self.blacklist = new_list
            if self.blacklist:
                print(f"\033[95m[AFH] Hop Engine Blacklist Updated: {self.blacklist}\033[0m", flush=True)
        except: pass

    def handle_trigger(self, msg):
        """Calculates frequency based on absolute system time with AFH remapping."""
        now = time.time()
        # Always target the NEXT epoch boundary to guarantee a future timestamp for UHD
        epoch = int(now / self.dwell_sec) + 1
        epoch_start_time = epoch * self.dwell_sec
        
        nonce = struct.pack(">QQ", 0, epoch)
        cipher = Cipher(algorithms.AES(self.key), modes.ECB(), backend=self.backend)
        encryptor = cipher.encryptor()
        keystream = encryptor.update(nonce) + encryptor.finalize()
        
        rand_val = struct.unpack(">I", keystream[:4])[0]
        raw_idx = rand_val % self.num_channels
        
        # AFH Remapping: If channel is blacklisted, find the next available clear one
        final_idx = raw_idx
        if self.blacklist and final_idx in self.blacklist:
            for i in range(1, self.num_channels):
                candidate = (raw_idx + i) % self.num_channels
                if candidate not in self.blacklist:
                    final_idx = candidate
                    break
        
        freq = self.center_freq + (final_idx - (self.num_channels // 2)) * self.channel_spacing
        
        # Log absolute time and channel for synchronization verification
        if final_idx != raw_idx:
            print(f"\033[96m[AFH Hop] {time.strftime('%H:%M:%S')} | EVADED {raw_idx} -> Moved to {final_idx}\033[0m")

        # Emit dict with freq and precise command time
        out_dict = pmt.make_dict()
        out_dict = pmt.dict_add(out_dict, pmt.intern("freq"), pmt.from_double(freq))
        out_dict = pmt.dict_add(out_dict, pmt.intern("time"), pmt.from_double(epoch_start_time))
        self.message_port_pub(pmt.intern("freq"), out_dict)

    def work(self, input_items, output_items):
        return 0
