#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Autonomous Tactical Session Manager (v12.7 - AFH Build)

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
    Handles Handshaking (SYN/ACK), ARQ Retries, and Cognitive AFH Evasion.
    """
    def __init__(self, initial_seed=0xACE, config_path="mission_configs/level1_soft_link.yaml"):
        gr.basic_block.__init__(self, name="session_manager", in_sig=None, out_sig=None)
        
        with open(config_path, 'r') as f: self.cfg = yaml.safe_load(f)
        mac_cfg = self.cfg.get('mac_layer', {})
        h_cfg = self.cfg.get('hopping', {})
        self.afh_enabled = mac_cfg.get('afh_enabled', False)
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
        
        # AFH (Cognitive) Logic
        self.afh_threshold = 5 # Consecutive packets failed before blacklisting
        self.channel_stats = {} # {freq: consecutive_failures}
        self.blacklist = []
        self.current_f = 0
        self.num_channels = h_cfg.get('num_channels', 50)
        self.center_freq = self.cfg.get('physical', {}).get('center_freq', 915e6)
        self.spacing = h_cfg.get('channel_spacing', 150e3)

        # Message Ports
        self.message_port_register_in(pmt.intern("msg_in"))
        self.set_msg_handler(pmt.intern("msg_in"), self.handle_rx)
        self.message_port_register_in(pmt.intern("freq_in"))
        self.set_msg_handler(pmt.intern("freq_in"), self.handle_freq_update)
        
        self.message_port_register_in(pmt.intern("data_in"))
        self.set_msg_handler(pmt.intern("data_in"), self.handle_tx_request)
        self.message_port_register_in(pmt.intern("manual_in"))
        self.set_msg_handler(pmt.intern("manual_in"), self.handle_tx_request)
        self.message_port_register_in(pmt.intern("crc_fail"))
        self.set_msg_handler(pmt.intern("crc_fail"), self.handle_crc_fail)
        
        # Heartbeat port for autonomous pulses
        self.message_port_register_in(pmt.intern("heartbeat"))
        self.set_msg_handler(pmt.intern("heartbeat"), self.handle_heartbeat)
        
        self.message_port_register_out(pmt.intern("pkt_out"))
        self.message_port_register_out(pmt.intern("data_out"))
        self.message_port_register_out(pmt.intern("status_out"))
        self.message_port_register_out(pmt.intern("afh_out")) # Blacklist updates

    def handle_freq_update(self, msg):
        """Monitors the active frequency from the hop engine."""
        self.current_f = pmt.to_double(pmt.dict_ref(msg, pmt.intern("freq"), pmt.from_double(0)))

    def apply_blacklist(self):
        """Pushes the current tactical blacklist to the hop generator."""
        msg = pmt.init_u8vector(len(self.blacklist), self.blacklist)
        self.message_port_pub(pmt.intern("afh_out"), msg)
        print(f"\033[95m[AFH] Applied Tactical Blacklist to Hop Engine: {self.blacklist}\033[0m", flush=True)

    def handle_heartbeat(self, msg):
        """Triggered by a message strobe to perform background tasks."""
        if self.state != "CONNECTED":
            # v19.22: Blast SYN packets to catch hopping peers
            print(f"[MAC] Searching for peer... (State: {self.state})")
            syn_payload = struct.pack('>H', self.current_seed).ljust(16, b'\x00')
            for _ in range(3): self.send_packet(syn_payload, msg_type=1)

    def publish_status(self):
        msg = pmt.make_dict()
        msg = pmt.dict_add(msg, pmt.intern("state"), pmt.intern(self.state))
        msg = pmt.dict_add(msg, pmt.intern("blacklist"), pmt.init_u8vector(len(self.blacklist), self.blacklist))
        self.message_port_pub(pmt.intern("status_out"), msg)

    def handle_rx(self, msg):
        # v19.25: Handle Diagnostic Messages (Link Health)
        if pmt.is_dict(msg):
            if pmt.dict_has_key(msg, pmt.intern("crc_ok")):
                ok = pmt.to_bool(pmt.dict_ref(msg, pmt.intern("crc_ok"), pmt.from_bool(False)))
                if not ok: self.handle_crc_fail(msg)
                else: self.consecutive_fails = 0
            return

        meta = pmt.car(msg)
        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        m_type = pmt.to_long(pmt.dict_ref(meta, pmt.intern("type"), pmt.from_long(0)))

        # CRITICAL FIX: Reset failure counters on ANY successful packet
        self.consecutive_fails = 0
        if self.current_f in self.channel_stats:
            self.channel_stats[self.current_f] = 0

        if m_type == 5: # TYPE_LEAP (Cognitive Sync)
            new_blacklist = list(payload)
            print(f"\033[93m[AFH] LEAP COMMAND RECEIVED. Syncing Blacklist: {new_blacklist}\033[0m", flush=True)
            self.blacklist = list(set(self.blacklist + new_blacklist))
            self.apply_blacklist()
            return

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
            # v19.25: Transparent Mode. Always pass DATA to UI, even if Handshake is pending.
            seq = pmt.to_long(pmt.dict_ref(meta, pmt.intern("seq"), pmt.from_long(0)))
            if self.arq_enabled: 
                for _ in range(2): self.send_packet(struct.pack('B', seq), msg_type=2)
            self.message_port_pub(pmt.intern("data_out"), msg)

    def handle_tx_request(self, msg):
        """Entry point for application-layer data."""
        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        if len(payload) > 0 and b"PING" not in payload:
            print(f"[MAC] Queuing Manual Tactical Data: {payload.decode('utf-8', errors='replace')}", flush=True)
            # Insert a tiny micro-delay to avoid colliding with an ongoing heartbeat pulse
            time.sleep(0.01) 
            
        if self.state == "CONNECTED":
            self.send_data_packet(msg)
        else:
            self.tx_buffer.append(msg)
            if self.state == "IDLE":
                self.state = "CONNECTING"
                self.publish_status()
                # Immediate wake-up burst
                syn_payload = struct.pack('>H', self.current_seed).ljust(16, b'\x00')
                for _ in range(3): self.send_packet(syn_payload, msg_type=1)

    def handle_crc_fail(self, msg):
        """Tracks link quality and handles autonomous evasion."""
        self.consecutive_fails += 1
        
        # Track failures per frequency
        if self.afh_enabled and self.current_f > 0:
            self.channel_stats[self.current_f] = self.channel_stats.get(self.current_f, 0) + 1
            if self.channel_stats[self.current_f] >= self.afh_threshold:
                # Calculate channel index
                idx = int(round((self.current_f - self.center_freq) / self.spacing) + (self.num_channels // 2))
                if 0 <= idx < self.num_channels and idx not in self.blacklist:
                    print(f"\033[91m[AFH] FREQUENCY JAMMED ({self.current_f/1e6:.2f} MHz). Triggering LEAP...\033[0m", flush=True)
                    self.blacklist.append(idx)
                    self.apply_blacklist()
                    # Broadcast LEAP to peer (Type 5)
                    self.send_packet(bytes(self.blacklist), msg_type=5)

        if self.consecutive_fails > 50: # Increased threshold for high-speed hopping
            print("\033[91m[MAC] Link Reliability Lost. Re-Synchronizing...\033[0m", flush=True)
            self.state = "CONNECTING"
            self.publish_status()

    def send_data_packet(self, msg):
        meta = pmt.car(msg)
        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(0))
        meta = pmt.dict_add(meta, pmt.intern("seq"), pmt.from_long(self.local_seq))
        self.local_seq = (self.local_seq + 1) & 0xFF
        if b"PING" not in payload:
            print(f"\033[94m[MAC] Dispatching DATA Frame ({len(payload)} bytes)...\033[0m", flush=True)
        self.message_port_pub(pmt.intern("pkt_out"), pmt.cons(meta, pmt.cdr(msg)))

    def send_packet(self, payload_bytes, msg_type):
        """Helper for emitting MAC-layer control frames."""
        meta = pmt.make_dict()
        meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(msg_type))
        blob = pmt.init_u8vector(len(payload_bytes), list(payload_bytes))
        self.message_port_pub(pmt.intern("pkt_out"), pmt.cons(meta, blob))

    def work(self, i, o): return 0
