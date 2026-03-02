#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Mission-Controlled Packetizer (with Sequence Tracking)

import numpy as np
from gnuradio import gr
import pmt
import struct
import os
import sys
import yaml
import binascii

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from rs_helper import RS1511, RS3115
from dsp_helper import MatrixInterleaver, DSSSProcessor, NRZIEncoder, ManchesterEncoder, Scrambler

class packetizer(gr.basic_block):
    def __init__(self, config_path="mission_configs/level1_soft_link.yaml"):
        gr.basic_block.__init__(self, name="packetizer", in_sig=None, out_sig=None)
        
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
            
        l_cfg = self.cfg['link_layer']
        self.crc_type = l_cfg.get('crc_type', "CRC16")
        self.use_fec = l_cfg.get('use_fec', True)
        self.use_interleaving = l_cfg.get('use_interleaving', True)
        self.use_whitening = l_cfg.get('use_whitening', True)
        self.use_manchester = l_cfg.get('use_manchester', False)
        self.use_nrzi = l_cfg.get('use_nrzi', True)
        self.use_dsss = self.cfg['dsss'].get('enabled', True)
        
        self.fec_mode = self.cfg.get('mission', {}).get('id', "")
        self.rs1511 = RS1511()
        self.rs3115 = RS3115()
        
        self.interleaver = MatrixInterleaver(rows=l_cfg.get('interleaver_rows', 8))
        self.scrambler = Scrambler(mask=l_cfg.get('scrambler_mask', 0x48), seed=l_cfg.get('scrambler_seed', 0x7F))
        self.manchester = ManchesterEncoder()
        self.nrzi = NRZIEncoder()
        self.dsss = DSSSProcessor(chipping_code=self.cfg['dsss']['chipping_code'])
        
        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)
        self.message_port_register_out(pmt.intern("out"))
        
        self.preamble = b'\xAA' * 32
        self.syncword = b'\x3D\x4C\x5B\x6A'
        self.sequence = 0

    def calculate_crc(self, data):
        if self.crc_type == "CRC16":
            crc = 0xFFFF
            for byte in data:
                crc ^= byte << 8
                for _ in range(8):
                    if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                    else: crc = (crc << 1)
                    crc &= 0xFFFF
            return struct.pack('>H', crc)
        elif self.crc_type == "CRC32":
            return struct.pack('>I', binascii.crc32(data) & 0xFFFFFFFF)
        return b''

    def handle_msg(self, msg):
        if not pmt.is_pdu(msg): return
        meta = pmt.car(msg)
        payload_bytes = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        
        msg_type = pmt.to_long(pmt.dict_ref(meta, pmt.intern("type"), pmt.from_long(0)))
        header = struct.pack('BBB', msg_type, self.sequence, len(payload_bytes) & 0xFF)
        self.sequence = (self.sequence + 1) & 0xFF
        
        if self.use_fec:
            if "LINK-16" in self.fec_mode:
                pad_len = (15 - (len(payload_bytes) % 15)) % 15
                padded = payload_bytes + b'\x00' * pad_len
                p_bits = []
                for b in padded:
                    for i in range(8): p_bits.append((b >> (7-i)) & 1)
                
                # Encode in 75-bit blocks (15 symbols x 5 bits)
                out_bits = []
                for i in range(0, len(p_bits), 75):
                    chunk = p_bits[i:i+75]
                    symbols = []
                    for j in range(len(chunk) // 5):
                        s = 0
                        for k in range(5): s = (s << 1) | chunk[j*5+k]
                        symbols.append(s)
                    # If the chunk was exactly 75 bits, we have 15 symbols.
                    # If it was less (shouldn't happen with our padding), symbols < 15.
                    # But RS3115.encode expects 15.
                    if len(symbols) < 15: symbols.extend([0] * (15 - len(symbols)))
                    
                    encoded = self.rs3115.encode(symbols) # 31 symbols
                    for s in encoded:
                        for k in range(5): out_bits.append((s >> (4-k)) & 1)
                
                fec_payload = []
                acc = 0; bc = 0
                for bit in out_bits:
                    acc = (acc << 1) | bit; bc += 1
                    if bc == 8: fec_payload.append(acc); acc = 0; bc = 0
                if bc > 0: fec_payload.append(acc << (8-bc))
                payload = bytes(fec_payload)
            else:
                pad_len = (11 - (len(payload_bytes) % 11)) % 11
                padded = payload_bytes + b'\x00' * pad_len
                fec_payload = b''
                for i in range(0, len(padded), 11):
                    chunk = padded[i:i+11]; nib = []
                    for b in chunk: nib.extend([(b >> 4) & 0x0F, b & 0x0F])
                    all_nib = self.rs1511.encode(nib[:11]) + self.rs1511.encode(nib[11:])
                    for j in range(0, 30, 2): fec_payload += bytes([(all_nib[j] << 4) | all_nib[j+1]])
                payload = fec_payload
        else:
            payload = payload_bytes

        data_block = header + payload
        data_block += self.calculate_crc(data_block)
        
        if self.use_interleaving:
            target_len = 256 if "LINK-16" in self.fec_mode or "LEVEL_6" in self.fec_mode else 120
            if len(data_block) < target_len: data_block += b'\x00' * (target_len - len(data_block))
            data_block = self.interleaver.interleave(data_block)
        
        if self.use_whitening: data_block = self.scrambler.process(data_block)
        
        final_bits = []
        for b in data_block:
            for i in range(8): final_bits.append((b >> (7-i)) & 1)
        if self.use_nrzi: self.nrzi.reset(); final_bits = self.nrzi.encode(final_bits)
        if self.use_manchester: self.manchester.reset(); final_bits = self.manchester.encode(final_bits)
        if self.use_dsss:
            chips = self.dsss.spread(final_bits); final_bits = [1 if c > 0 else 0 for c in chips]

        packed_out = []
        acc = 0; bc = 0
        for bit in final_bits:
            acc = (acc << 1) | bit; bc += 1
            if bc == 8: packed_out.append(acc); acc = 0; bc = 0
        if bc > 0: packed_out.append(acc << (8-bc))
        # 10. Final Assembly
        packet = self.preamble + self.syncword + bytes(packed_out) + b'\x00' * 32
        
        # Log to console
        print(f"\033[95m[TX] Sending Packet | ID: {self.sequence-1:03} | Len: {len(packet)} bytes\033[0m")
        
        self.message_port_pub(pmt.intern("out"), pmt.cons(meta, pmt.init_u8vector(len(packet), list(packet))))
