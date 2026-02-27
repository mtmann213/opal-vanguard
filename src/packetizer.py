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
from rs_helper import RS1511
from dsp_helper import MatrixInterleaver, DSSSProcessor, NRZIEncoder, ManchesterEncoder, Scrambler

class packetizer(gr.basic_block):
    def __init__(self, config_path="config.yaml"):
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
        
        self.rs = RS1511()
        self.interleaver = MatrixInterleaver(rows=l_cfg.get('interleaver_rows', 8))
        self.scrambler = Scrambler(mask=l_cfg.get('scrambler_mask', 0x48), seed=l_cfg.get('scrambler_seed', 0x7F))
        self.manchester = ManchesterEncoder()
        self.nrzi = NRZIEncoder()
        self.dsss = DSSSProcessor(chipping_code=self.cfg['dsss']['chipping_code'])
        
        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)
        self.message_port_register_out(pmt.intern("out"))
        
        self.preamble = b'\xAA' * 8
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

        # 1. FEC (Reed-Solomon)
        if self.use_fec:
            pad_len = (11 - (len(payload_bytes) % 11)) % 11
            padded = payload_bytes + b'\x00' * pad_len
            fec_payload = b''
            for i in range(0, len(padded), 11):
                chunk = padded[i:i+11]
                nib = []
                for b in chunk: nib.extend([(b >> 4) & 0x0F, b & 0x0F])
                all_nib = self.rs.encode(nib[:11]) + self.rs.encode(nib[11:])
                for j in range(0, 30, 2):
                    fec_payload += bytes([(all_nib[j] << 4) | all_nib[j+1]])
            payload = fec_payload
        else:
            payload = payload_bytes
            
        # 2. Add Header (Type, Sequence, Length) and CRC
        # Increased header to 3 bytes to support scoring
        data_block = struct.pack('BBB', msg_type, self.sequence, len(payload_bytes) & 0xFF) + payload
        data_block += self.calculate_crc(data_block)
        
        # Increment sequence for tracking
        self.sequence = (self.sequence + 1) & 0xFF
        
        # 3. Interleave
        if self.use_interleaving:
            if len(data_block) < 120: data_block += b'\x00' * (120 - len(data_block))
            data_block = self.interleaver.interleave(data_block)
        
        # 4. Whiten (Scramble)
        if self.use_whitening: data_block = self.scrambler.process(data_block)
            
        # 5. Bit-Level Processing
        bits = []
        for b in data_block:
            for i in range(8): bits.append((b >> (7-i)) & 1)
            
        # 6. NRZ-I
        if self.use_nrzi:
            self.nrzi.reset()
            bits = self.nrzi.encode(bits)
            
        # 7. Manchester
        if self.use_manchester:
            self.manchester.reset()
            bits = self.manchester.encode(bits)
            
        # 8. DSSS
        if self.use_dsss:
            chips = self.dsss.spread(bits)
            bits = [1 if c > 0 else 0 for c in chips]

        # 9. Pack to Bytes
        packed_data = []
        current_byte = 0
        for i, bit in enumerate(bits):
            current_byte = (current_byte << 1) | bit
            if (i + 1) % 8 == 0:
                packed_data.append(current_byte); current_byte = 0
        if len(bits) % 8 != 0:
            packed_data.append(current_byte << (8 - (len(bits) % 8)))
        
        # 10. Final Assembly
        packet = self.preamble + self.syncword + bytes(packed_data) + b'\x00' * 32
        self.message_port_pub(pmt.intern("out"), pmt.cons(meta, pmt.init_u8vector(len(packet), list(packet))))
