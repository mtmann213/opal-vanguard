#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Session Manager (with Seed Sync)

import numpy as np
from gnuradio import gr
import pmt
import time
import struct

class session_manager(gr.basic_block):
    def __init__(self, initial_seed=0xACE):
        gr.basic_block.__init__(self, name="session_manager", in_sig=None, out_sig=None)
        
        self.message_port_register_in(pmt.intern("msg_in"))
        self.set_msg_handler(pmt.intern("msg_in"), self.handle_rx)
        
        self.message_port_register_in(pmt.intern("data_in"))
        self.set_msg_handler(pmt.intern("data_in"), self.handle_tx_request)
        
        self.message_port_register_out(pmt.intern("pkt_out"))
        self.message_port_register_out(pmt.intern("data_out"))
        self.message_port_register_out(pmt.intern("set_seed")) # To Hop Controller
        
        self.state = "IDLE"
        self.current_seed = initial_seed

    def handle_rx(self, msg):
        meta = pmt.car(msg)
        msg_type = pmt.to_long(pmt.dict_ref(meta, pmt.intern("type"), pmt.from_long(0)))
        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))

        elif msg_type == 1: # SYN received (Payload contains 2-byte seed)
            try:
                remote_seed = struct.unpack('>H', payload)[0]
                print(f"[Session] Received SYN with Seed: 0x{remote_seed:04X}. Sending ACK.")
                self.current_seed = remote_seed
                
                # Sync our local hop controller (if port is connected)
                self.message_port_pub(pmt.intern("set_seed"), pmt.from_long(self.current_seed))
            except Exception as e:
                print(f"[Session] Seed Sync Error: {e}")
            
            self.send_packet(b"ACK", msg_type=2)
            self.state = "CONNECTED"
                
        elif msg_type == 2: # ACK received
            if self.state == "CONNECTING":
                print("[Session] Received ACK. Seed confirmed. Connection Established.")
                self.state = "CONNECTED"
                
        elif msg_type == 0: # DATA received
            if self.state == "CONNECTED":
                self.message_port_pub(pmt.intern("data_out"), msg)

    def handle_tx_request(self, msg):
        if self.state == "CONNECTED":
            new_meta = pmt.dict_add(pmt.car(msg), pmt.intern("type"), pmt.from_long(0))
            self.message_port_pub(pmt.intern("pkt_out"), pmt.cons(new_meta, pmt.cdr(msg)))
        else:
            print(f"[Session] Initiating Handshake with Seed: 0x{self.current_seed:04X}")
            self.state = "CONNECTING"
            # SYN payload is the 2-byte seed
            seed_payload = struct.pack('>H', self.current_seed)
            self.send_packet(seed_payload, msg_type=1)

    def send_packet(self, payload_bytes, msg_type):
        meta = pmt.make_dict()
        meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(msg_type))
        blob = pmt.init_u8vector(len(payload_bytes), list(payload_bytes))
        self.message_port_pub(pmt.intern("pkt_out"), pmt.cons(meta, blob))

    def work(self, input_items, output_items):
        return 0
