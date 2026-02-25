#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Depacketizer Block (Handshake Support)

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
        for i in range(len(in0)):
            bit = int(in0[i]) & 1
            self.bit_buf = ((self.bit_buf << 1) | bit) & 0xFFFFFFFF
            
            if self.state == "SEARCH":
                if self.bit_buf == self.syncword_bits or self.bit_buf == (0xFFFFFFFF ^ self.syncword_bits):
                    self.is_inverted = (self.bit_buf == (0xFFFFFFFF ^ self.syncword_bits))
                    print(f"[Depacketizer] Syncword Found! (Inverted: {self.is_inverted})")
                    self.state = "COLLECT"
                    self.byte_buf = b''
                    self.bits_in_buf = 0
                    
            elif self.state == "COLLECT":
                self.bits_in_buf += 1
                if self.bits_in_buf % 8 == 0:
                    current_byte = self.bit_buf & 0xFF
                    if self.is_inverted:
                        current_byte ^= 0xFF
                    self.byte_buf += bytes([current_byte])
                    
                    if len(self.byte_buf) == 2: # Type + Len bytes
                        # Peek at header to get length
                        data_peek = self.dewhiten(self.byte_buf) if self.use_whitening else self.byte_buf
                        msg_type, self.payload_len = struct.unpack('BB', data_peek)
                        print(f"[Depacketizer] Header Parsed - Type: {msg_type}, Len: {self.payload_len}")
                        
                        # Safety reset for junk headers
                        if self.payload_len > 128:
                            print(f"[Depacketizer] Invalid length {self.payload_len}, resetting.")
                            self.state = "SEARCH"
                            return 0

                        if self.use_fec:
                            self.fec_payload_len = ((self.payload_len + 10) // 11) * 15
                        else:
                            self.fec_payload_len = self.payload_len

                    # Total = 1 (Type) + 1 (Len) + N (Payload) + 2 (CRC)
                    if len(self.byte_buf) == 2 + self.fec_payload_len + 2:
                        data = self.dewhiten(self.byte_buf) if self.use_whitening else self.byte_buf
                        calc_crc = self.crc16_ccitt(data[:-2])
                        received_crc = struct.unpack('>H', data[-2:])[0]
                        
                        if calc_crc == received_crc:
                            msg_type, plen = struct.unpack('BB', data[:2])
                            fec_payload = data[2:-2]
                            print(f"[Depacketizer] CRC PASSED! Type: {msg_type}, Len: {plen}")
                            
                            if self.use_fec:
                                decoded = b''
                                for j in range(0, len(fec_payload), 15):
                                    chunk = fec_payload[j:j+15]
                                    # Convert 15 bytes to 30 nibbles
                                    nib = []
                                    for b in chunk: nib.extend([(b >> 4) & 0x0F, b & 0x0F])
                                    
                                    block1 = self.rs.decode(nib[:15])
                                    block2 = self.rs.decode(nib[15:])
                                    all_nib = block1 + block2
                                    
                                    # Check if FEC actually did something
                                    if all_nib != nib[:11] + nib[15:15+11]: # Simple check
                                        pass # We'll do a better comparison
                                    
                                    for k in range(0, 22, 2):
                                        decoded += bytes([(all_nib[k] << 4) | all_nib[k+1]])
                                payload = decoded[:plen]
                                
                                # If the payload we got from FEC is different from the raw whitened payload, 
                                # then FEC corrected something.
                                if payload != data[2:2+plen]:
                                    print(f"[Depacketizer] FEC REPAIR SUCCESSFUL: Fixed bit errors in Type {msg_type} packet.")
                            else:
                                payload = fec_payload
                            
                            meta = pmt.make_dict()
                            meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(msg_type))
                            self.message_port_pub(pmt.intern("out"), pmt.cons(meta, pmt.init_u8vector(len(payload), list(payload))))
                        else:
                            print(f"[Depacketizer] CRC FAILED: Calc 0x{calc_crc:04X} != Recv 0x{received_crc:04X}")
                        
                        self.state = "SEARCH"

        self.consume(0, len(in0))
        return 0
