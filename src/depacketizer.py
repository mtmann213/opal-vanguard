#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Depacketizer Block (with RS FEC & Internal De-whitening)

import numpy as np
from gnuradio import gr
import pmt
import struct
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from rs_helper import RS1511

class depacketizer(gr.basic_block):
    def __init__(self, use_fec=True, use_whitening=True):
        gr.basic_block.__init__(self, name="depacketizer", in_sig=[np.uint8], out_sig=None)
        self.use_fec = use_fec
        self.use_whitening = use_whitening
        self.rs = RS1511()
        
        self.message_port_register_out(pmt.intern("out"))
        
        # State Machine
        self.state = "SEARCH"
        self.syncword_bits = 0x3D4C5B6A
        self.bit_buf = 0
        self.bits_in_buf = 0
        self.byte_buf = b''
        self.payload_len = 0
        self.fec_payload_len = 0

    def dewhiten(self, data):
        state = 0x7F
        out = []
        for byte in data:
            new_byte = 0
            for i in range(8):
                feedback = ((state >> 6) ^ (state >> 3)) & 1
                bit = (byte >> (7-i)) & 1
                dewhitened_bit = bit ^ (state & 1)
                new_byte = (new_byte << 1) | dewhitened_bit
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
        return crc

    def general_work(self, input_items, output_items):
        in0 = input_items[0]
        n = len(in0)
        
        for i in range(n):
            bit = int(in0[i]) & 1
            self.bit_buf = ((self.bit_buf << 1) | bit) & 0xFFFFFFFF
            
            if self.state == "SEARCH":
                if self.bit_buf == self.syncword_bits:
                    self.state = "COLLECT"
                    self.byte_buf = b''
                    self.bits_in_buf = 0
                    
            elif self.state == "COLLECT":
                # Collect bits into bytes for processing
                self.bits_in_buf += 1
                if self.bits_in_buf % 8 == 0:
                    byte_val = self.bit_buf & 0xFF
                    self.byte_buf += bytes([byte_val])
                    
                    # Once we have the first byte (whitened length), peek at it
                    if len(self.byte_buf) == 1:
                        # De-whiten first byte to get payload length
                        whitened_len = self.byte_buf[0]
                        state = 0x7F
                        orig_len = 0
                        for j in range(8):
                            feedback = ((state >> 6) ^ (state >> 3)) & 1
                            bit_val = (whitened_len >> (7-j)) & 1
                            orig_len = (orig_len << 1) | (bit_val ^ (state & 1))
                            state = ((state << 1) & 0x7F) | feedback
                        self.payload_len = orig_len
                        if self.use_fec:
                            self.fec_payload_len = ((self.payload_len + 10) // 11) * 15
                        else:
                            self.fec_payload_len = self.payload_len

                    # Total frame length = 1 (Len) + N (Payload) + 2 (CRC)
                    if len(self.byte_buf) == 1 + self.fec_payload_len + 2:
                        # Full packet collected, now de-whiten and check
                        if self.use_whitening:
                            data_part = self.dewhiten(self.byte_buf)
                        else:
                            data_part = self.byte_buf
                        
                        len_header = data_part[0]
                        fec_payload = data_part[1:-2]
                        received_crc = struct.unpack('>H', data_part[-2:])[0]
                        calc_crc = self.crc16_ccitt(data_part[:-2])
                        
                        if calc_crc == received_crc:
                            if self.use_fec:
                                decoded_payload = b''
                                for j in range(0, len(fec_payload), 15):
                                    chunk = fec_payload[j:j+15]
                                    nib = []
                                    for b in chunk:
                                        nib.extend([(b >> 4) & 0x0F, b & 0x0F])
                                    dec1 = self.rs.decode(nib[:15])
                                    dec2 = self.rs.decode(nib[15:])
                                    all_nib = dec1 + dec2
                                    for k in range(0, 22, 2):
                                        decoded_payload += bytes([(all_nib[k] << 4) | all_nib[k+1]])
                                final_payload = decoded_payload[:len_header]
                            else:
                                final_payload = fec_payload
                            
                            self.message_port_pub(pmt.intern("out"), pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(final_payload), list(final_payload))))
                        
                        self.state = "SEARCH"

        self.consume(0, n)
        return 0
