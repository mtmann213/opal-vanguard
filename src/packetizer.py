#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Packetizer Block (with RS FEC & Internal Whitening)

import numpy as np
from gnuradio import gr
import pmt
import struct
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from rs_helper import RS1511

class packetizer(gr.basic_block):
    def __init__(self, use_fec=True, use_whitening=True):
        gr.basic_block.__init__(self, name="packetizer", in_sig=None, out_sig=None)
        self.use_fec = use_fec
        self.use_whitening = use_whitening
        self.rs = RS1511()
        
        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)
        self.message_port_register_out(pmt.intern("out"))
        
        self.preamble = b'\xAA\xAA'
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
        payload_bytes = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        
        # 1. FEC
        if self.use_fec:
            pad_len = (11 - (len(payload_bytes) % 11)) % 11
            padded = payload_bytes + b'\x00' * pad_len
            fec_payload = b''
            for i in range(0, len(padded), 11):
                chunk = padded[i:i+11]
                nib = []
                for b in chunk:
                    nib.extend([(b >> 4) & 0x0F, b & 0x0F])
                all_nib = self.rs.encode(nib[:11]) + self.rs.encode(nib[11:])
                for j in range(0, 30, 2):
                    fec_payload += bytes([(all_nib[j] << 4) | all_nib[j+1]])
            payload = fec_payload
        else:
            payload = payload_bytes
            
        # 2. Assemble Header + Payload + CRC
        header_payload_crc = struct.pack('B', len(payload_bytes) & 0xFF) + payload
        header_payload_crc += self.crc16_ccitt(header_payload_crc)
        
        # 3. Whiten only the data part (not preamble/sync)
        if self.use_whitening:
            data_part = self.whiten(header_payload_crc)
        else:
            data_part = header_payload_crc
            
        packet = self.preamble + self.syncword + data_part
        out_msg = pmt.cons(pmt.car(msg), pmt.init_u8vector(len(packet), list(packet)))
        self.message_port_pub(pmt.intern("out"), out_msg)
