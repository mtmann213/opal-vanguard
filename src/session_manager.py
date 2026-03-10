#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Autonomous Tactical Session Manager (v12.5)

import numpy as np
from gnuradio import gr
import pmt
import struct
import time
import yaml
import os

class session_manager(gr.basic_block):
    """
    Tactical MAC Layer for Opal Vanguard.
    Handles Handshaking (SYN/ACK), ARQ Retries, and Link Quality Monitoring.
    """
    def __init__(self, initial_seed=0xACE, config_path="mission_configs/level1_soft_link.yaml"):
        gr.basic_block.__init__(self, name="session_manager", in_sig=None, out_sig=None)
        
        with open(config_path, 'r') as f: self.cfg = yaml.safe_load(f)
        mac_cfg = self.cfg.get('mac_layer', {})
        self.arq_enabled = mac_cfg.get('arq_enabled', True)
        self.max_retries = mac_cfg.get('max_retries', 3)
        
        # Internal State
        self.state = "IDLE"
        self.current_seed = initial_seed
        self.tx_buffer = []
        self.sent_history = {}
        self.local_seq = 0
        self.last_pulse = 0
        self.consecutive_fails = 0

        # Message Ports
        self.message_port_register_in(pmt.intern("msg_in"))
        self.set_msg_handler(pmt.intern("msg_in"), self.handle_rx)
        self.message_port_register_in(pmt.intern("data_in"))
        self.set_msg_handler(pmt.intern("data_in"), self.handle_tx_request)
        self.message_port_register_in(pmt.intern("manual_in"))
        self.set_msg_handler(pmt.intern("manual_in"), self.handle_tx_request)
        self.message_port_register_in(pmt.intern("crc_fail"))
        self.set_msg_handler(pmt.intern("crc_fail"), self.handle_crc_fail)
        
        # New: Heartbeat port for autonomous pulses
        self.message_port_register_in(pmt.intern("heartbeat"))
        self.set_msg_handler(pmt.intern("heartbeat"), self.handle_heartbeat)
        
        self.message_port_register_out(pmt.intern("pkt_out"))
        self.message_port_register_out(pmt.intern("data_out"))
        self.message_port_register_out(pmt.intern("status_out"))

    def handle_heartbeat(self, msg):
        """Triggered by a message strobe to perform background tasks."""
        if self.state != "CONNECTED":
            syn_payload = struct.pack('>H', self.current_seed).ljust(16, b'\x00')
            self.send_packet(syn_payload, msg_type=1)

    def publish_status(self):
        msg = pmt.make_dict()
        msg = pmt.dict_add(msg, pmt.intern("state"), pmt.intern(self.state))
        self.message_port_pub(pmt.intern("status_out"), msg)

    def handle_rx(self, msg):
        meta = pmt.car(msg)
        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        m_type = pmt.to_long(pmt.dict_ref(meta, pmt.intern("type"), pmt.from_long(0)))

        if m_type == 1: # Handshake SYN
            if self.state != "CONNECTED":
                print(f"[MAC] Handshake SYN Detected. Responding with High-Availability ACK.")
                for _ in range(5): self.send_packet(b"ACK", msg_type=2) # Blast ACKs to ensure capture
                self.state = "CONNECTED"
                self.publish_status()
        
        elif m_type == 2: # Handshake ACK
            if self.state != "CONNECTED":
                print("\033[96m[MAC] Handshake ACK Received. Secure Link Established.\033[0m")
                self.state = "CONNECTED"
                self.publish_status()
                # Flush transmission buffer
                while self.tx_buffer: self.send_data_packet(self.tx_buffer.pop(0))

        elif m_type == 0: # DATA
            if self.state == "CONNECTED":
                self.consecutive_fails = 0
                seq = pmt.to_long(pmt.dict_ref(meta, pmt.intern("seq"), pmt.from_long(0)))
                # Blast multiple ACKs for data confirmation in high-speed modes
                if self.arq_enabled: 
                    for _ in range(2): self.send_packet(struct.pack('B', seq), msg_type=2)
                self.message_port_pub(pmt.intern("data_out"), msg)

    def handle_tx_request(self, msg):
        """Entry point for application-layer data."""
        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        if len(payload) > 0 and b"PING" not in payload:
            print(f"[MAC] Queuing Manual Tactical Data: {payload.decode('utf-8', errors='replace')}")
            # Insert a tiny micro-delay to avoid colliding with an ongoing heartbeat pulse
            time.sleep(0.01) 
            
        if self.state == "CONNECTED":
            self.send_data_packet(msg)
        else:
            self.tx_buffer.append(msg)
            if self.state == "IDLE":
                self.state = "CONNECTING"
                self.publish_status()

    def handle_crc_fail(self, msg):
        """Tracks link quality and handles NACKs."""
        self.consecutive_fails += 1
        if self.consecutive_fails > 50: # Increased threshold for high-speed hopping
            print("\033[91m[MAC] Link Reliability Lost. Re-Synchronizing...\033[0m")
            self.state = "CONNECTING"
            self.publish_status()

    def send_data_packet(self, msg):
        meta = pmt.car(msg)
        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(0))
        meta = pmt.dict_add(meta, pmt.intern("seq"), pmt.from_long(self.local_seq))
        self.local_seq = (self.local_seq + 1) & 0xFF
        if b"PING" not in payload:
            print(f"\033[94m[MAC] Dispatching DATA Frame ({len(payload)} bytes)...\033[0m")
        self.message_port_pub(pmt.intern("pkt_out"), pmt.cons(meta, pmt.cdr(msg)))

    def send_packet(self, payload_bytes, msg_type):
        """Helper for emitting MAC-layer control frames."""
        meta = pmt.make_dict()
        meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(msg_type))
        blob = pmt.init_u8vector(len(payload_bytes), list(payload_bytes))
        self.message_port_pub(pmt.intern("pkt_out"), pmt.cons(meta, blob))

    def work(self, i, o): return 0
