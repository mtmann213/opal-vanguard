#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Session Manager (Mission Master Build v3.0)

import numpy as np
from gnuradio import gr
import pmt
import time
import struct
import yaml

class session_manager(gr.basic_block):
    def __init__(self, initial_seed=0xACE, config_path=None):
        gr.basic_block.__init__(self, name="session_manager", in_sig=None, out_sig=None)
        
        self.cfg = {}
        if config_path:
            with open(config_path, 'r') as f: self.cfg = yaml.safe_load(f)
        
        m_cfg = self.cfg.get('mac_layer', {})
        self.arq_enabled = m_cfg.get('arq_enabled', False)
        self.afh_enabled = m_cfg.get('afh_enabled', True)
        self.amc_enabled = m_cfg.get('amc_enabled', False)
        self.max_retries = m_cfg.get('max_retries', 3)
        
        # Ports
        self.message_port_register_in(pmt.intern("msg_in"))
        self.set_msg_handler(pmt.intern("msg_in"), self.handle_rx)
        self.message_port_register_in(pmt.intern("data_in"))
        self.set_msg_handler(pmt.intern("data_in"), self.handle_tx_request)
        self.message_port_register_in(pmt.intern("crc_fail"))
        self.set_msg_handler(pmt.intern("crc_fail"), self.handle_crc_fail)
        
        self.message_port_register_out(pmt.intern("pkt_out"))
        self.message_port_register_out(pmt.intern("data_out"))
        self.message_port_register_out(pmt.intern("set_seed"))
        self.message_port_register_out(pmt.intern("blacklist_out"))
        self.message_port_register_out(pmt.intern("amc_fallback")) # Tells top_block to restart
        
        self.state = "IDLE"; self.current_seed = initial_seed
        self.tx_buffer = []; self.sent_history = {}; self.local_seq = 0
        self.blacklist = set(); self.channel_strikes = {}
        
        # Link Quality Indicator (LQI) for AMC
        self.consecutive_fails = 0
        self.amc_triggered = False
def handle_rx(self, msg):
    meta = pmt.car(msg)
    payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
    m_type = pmt.to_long(pmt.dict_ref(meta, pmt.intern("type"), pmt.from_long(0)))

    # Diagnostic Handshake Tracer
    type_names = {0:"DATA", 1:"SYN", 2:"ACK", 3:"NACK", 4:"AFH", 5:"AMC"}
    print(f"[SESSION] RX {type_names.get(m_type, 'UNK')} | State: {self.state}")

    if m_type == 1: # SYN

            try:
                peer_seed = struct.unpack('>H', payload[:2])[0]
                self.current_seed = peer_seed
                print(f"\033[96m[MAC] Handshake SYN Received. Seed: 0x{peer_seed:04X}\033[0m")
            except: pass
            # Always reply with ACK to clear the peer's CONNECTING state
            self.send_packet(b"ACK", msg_type=2)
            self.state = "CONNECTED"
            self.consecutive_fails = 0
        elif m_type == 2: # ACK
            if self.state == "CONNECTING" or self.state == "IDLE":
                print("\033[96m[MAC] Handshake ACK Received. Session Connected.\033[0m")
                self.state = "CONNECTED"
                self.consecutive_fails = 0
                while self.tx_buffer: self.send_data_packet(self.tx_buffer.pop(0))
            try:
                seq = struct.unpack('B', payload)[0]
                if seq in self.sent_history: del self.sent_history[seq]
            except: pass
        elif m_type == 3: # NACK
            if self.arq_enabled:
                try:
                    seq = struct.unpack('B', payload)[0]
                    if seq in self.sent_history:
                        pdu, retries = self.sent_history[seq]
                        if retries < self.max_retries:
                            self.sent_history[seq] = (pdu, retries + 1)
                            self.message_port_pub(pmt.intern("pkt_out"), pdu)
                except: pass
        elif m_type == 4: # AFH UPDATE
            if self.afh_enabled:
                bl = list(payload)
                if set(bl) != self.blacklist:
                    self.blacklist = set(bl)
                    self.message_port_pub(pmt.intern("blacklist_out"), pmt.init_u8vector(len(bl), bl))
                    print(f"\033[96m[MAC] Blacklist Synced: {bl}\033[0m")
        elif m_type == 5: # AMC FALLBACK REQ
            if self.amc_enabled and not self.amc_triggered:
                print("\033[41m[AMC] PEER REQUESTED MODULATION FALLBACK. INITIATING REBOOT.\033[0m")
                self.amc_triggered = True
                self.message_port_pub(pmt.intern("amc_fallback"), pmt.PMT_T)
        elif m_type == 0: # DATA
            if self.state == "CONNECTED":
                self.consecutive_fails = 0 # Reset fail counter on good data
                seq = pmt.to_long(pmt.dict_ref(meta, pmt.intern("seq"), pmt.from_long(0)))
                if self.arq_enabled: self.send_packet(struct.pack('B', seq), msg_type=2)
                self.message_port_pub(pmt.intern("data_out"), msg)

    def handle_tx_request(self, msg):
        if self.state == "CONNECTED": self.send_data_packet(msg)
        else:
            self.tx_buffer.append(msg)
            if self.state == "IDLE" or self.state == "CONNECTING":
                self.state = "CONNECTING"
                # Pad SYN to 16 bytes for COMSEC reliability
                syn_payload = struct.pack('>H', self.current_seed).ljust(16, b'\x00')
                self.send_packet(syn_payload, msg_type=1)

    def handle_crc_fail(self, msg):
        # 1. ARQ NACK
        if self.arq_enabled:
            seq = pmt.to_long(pmt.dict_ref(msg, pmt.intern("seq"), pmt.from_long(255)))
            if seq != 255: self.send_packet(struct.pack('B', seq), msg_type=3)
        
        # 2. AFH Strike System
        if self.afh_enabled:
            chan = pmt.to_long(pmt.dict_ref(msg, pmt.intern("channel"), pmt.from_long(-1)))
            conf = pmt.to_double(pmt.dict_ref(msg, pmt.intern("confidence"), pmt.from_double(100.0)))
            
            if chan != -1:
                # CRC Fail or Low Confidence = Strike
                if not pmt.to_bool(pmt.dict_ref(msg, pmt.intern("crc_ok"), pmt.from_bool(False))) or conf < 40.0:
                    self.channel_strikes[chan] = self.channel_strikes.get(chan, 0) + 1
                    if self.channel_strikes[chan] >= 3: # 3 Strikes = Blacklisted
                        self.update_blacklist(chan)
                        
        # 3. AMC LQI Tracker
        if self.amc_enabled and not self.amc_triggered:
            self.consecutive_fails += 1
            if self.consecutive_fails >= 5: # Threshold for total link failure
                print("\033[41m[AMC] LINK QUALITY CRITICAL. REQUESTING PHY FALLBACK.\033[0m")
                self.amc_triggered = True
                self.send_packet(b"AMC", msg_type=5)
                # Give peer 500ms to receive the request, then restart local
                time.sleep(0.5)
                self.message_port_pub(pmt.intern("amc_fallback"), pmt.PMT_T)

    def update_blacklist(self, channel_idx):
        if channel_idx not in self.blacklist:
            self.blacklist.add(channel_idx)
            bl_list = sorted(list(self.blacklist))
            self.message_port_pub(pmt.intern("blacklist_out"), pmt.init_u8vector(len(bl_list), bl_list))
            self.send_packet(bytes(bl_list), msg_type=4) # Inform Peer
            print(f"\033[91m[AFH] CHANNEL {channel_idx} STAINED. Blacklisting and Syncing.\033[0m")

    def send_data_packet(self, msg):
        meta = pmt.car(msg)
        meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(0))
        meta = pmt.dict_add(meta, pmt.intern("seq"), pmt.from_long(self.local_seq))
        out_pdu = pmt.cons(meta, pmt.cdr(msg))
        if self.arq_enabled: self.sent_history[self.local_seq] = (out_pdu, 0)
        self.local_seq = (self.local_seq + 1) & 0xFF
        self.message_port_pub(pmt.intern("pkt_out"), out_pdu)

    def send_packet(self, payload_bytes, msg_type):
        meta = pmt.make_dict()
        meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(msg_type))
        blob = pmt.init_u8vector(len(payload_bytes), list(payload_bytes))
        self.message_port_pub(pmt.intern("pkt_out"), pmt.cons(meta, blob))

    def work(self, input_items, output_items): return 0
