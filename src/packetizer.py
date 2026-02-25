#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Packetizer Block (DSSS + Config Support)

import numpy as np
from gnuradio import gr
import pmt
import struct
import os
import sys
import yaml

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from rs_helper import RS1511
from dsp_helper import MatrixInterleaver, DSSSProcessor

class packetizer(gr.basic_block):
    def __init__(self, config_path="config.yaml"):
        gr.basic_block.__init__(self, name="packetizer", in_sig=None, out_sig=None)
        
        # Load Config
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
            
        self.use_fec = self.cfg['link_layer']['use_fec']
        self.use_whitening = self.cfg['link_layer']['use_whitening']
        self.use_interleaving = self.cfg['link_layer']['use_interleaving']
        self.use_dsss = self.cfg['link_layer']['use_dsss']
        
        self.rs = RS1511()
        self.interleaver = MatrixInterleaver(rows=8)
        self.dsss = DSSSProcessor(chipping_code=self.cfg['dsss']['chipping_code'])
        
        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)
        self.message_port_register_out(pmt.intern("out"))
        
        self.preamble = b'\xAA' * 8
        self.syncword = b'\x3D\x4C\x5B\x6A'

    def whiten(self, data):
        state = 0x7F
        out = []
        for byte in data:
            new_byte = 0
            for i in range(8):
                feedback = ((state >> 6) ^ (state >> 3)) & 1
                bit = (byte >> (7-i)) & 1
                whitened_bit = bit ^ (state & 1)
                new_byte = (new_byte << 1) | whitened_bit
                state = ((state << 1) & 0x7F) | feedback
            out.append(new_byte)
        return bytes(out)

    def crc16_ccitt(self, data):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                else: crc = (crc << 1)
                crc &= 0xFFFF
        return struct.pack('>H', crc)

    def handle_msg(self, msg):
        if not pmt.is_pdu(msg): return
        meta = pmt.car(msg)
        payload_bytes = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        
        msg_type = 0x00
        if pmt.dict_has_key(meta, pmt.intern("type")):
            msg_type = pmt.to_long(pmt.dict_ref(meta, pmt.intern("type"), pmt.from_long(0)))

        # 1. FEC
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
            
        # 2. Header + CRC
        data_to_whiten = struct.pack('BB', msg_type, len(payload_bytes) & 0xFF) + payload
        data_to_whiten += self.crc16_ccitt(data_to_whiten)
        
        # 3. Interleave
        if self.use_interleaving:
            data_to_whiten = self.interleaver.interleave(data_to_whiten)
        
        # 4. Whiten
        if self.use_whitening:
            data_final = self.whiten(data_to_whiten)
        else:
            data_final = data_to_whiten
            
        # 5. DSSS Spreading (Only on the data part)
        if self.use_dsss:
            # Convert bytes to bits
            bits = []
            for b in data_final:
                for i in range(8):
                    bits.append((b >> (7-i)) & 1)
            
            # Spread bits to chips
            chips = self.dsss.spread(bits)
            
            # Pack chips (-1/1) back into bytes for the GFSK modulator
            # Note: GFSK mod with do_unpack=True expects 0/1 bits packed in bytes.
            # We must map our bipolar chips back to 0/1 for the standard modulator.
            packed_chips = []
            current_byte = 0
            for i, chip in enumerate(chips):
                bit = 1 if chip > 0 else 0
                current_byte = (current_byte << 1) | bit
                if (i + 1) % 8 == 0:
                    packed_chips.append(current_byte)
                    current_byte = 0
            # Handle remaining bits if not multiple of 8
            if len(chips) % 8 != 0:
                packed_chips.append(current_byte << (8 - (len(chips) % 8)))
            
            data_part = bytes(packed_chips)
        else:
            data_part = data_final

        # 6. Final Assembly (Preamble and Syncword are NEVER spread)
        packet = self.preamble + self.syncword + data_part + b'\x00' * 32
        out_msg = pmt.cons(meta, pmt.init_u8vector(len(packet), list(packet)))
        self.message_port_pub(pmt.intern("out"), out_msg)
