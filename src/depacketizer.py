#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Depacketizer Block (Handshake + Interleaving Support)

import numpy as np
from gnuradio import gr
import pmt
import struct
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from rs_helper import RS1511
from dsp_helper import MatrixInterleaver

class depacketizer(gr.basic_block):
    def __init__(self, use_fec=True, use_whitening=True, use_interleaving=True):
        gr.basic_block.__init__(self, name="depacketizer", in_sig=[np.uint8], out_sig=None)
        self.use_fec = use_fec
        self.use_whitening = use_whitening
        self.use_interleaving = use_interleaving
        self.rs = RS1511()
        self.interleaver = MatrixInterleaver(rows=8)
        
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
                    self.fec_payload_len = 0 # Reset for new packet
                    
            elif self.state == "COLLECT":
                self.bits_in_buf += 1
                if self.bits_in_buf % 8 == 0:
                    current_byte = self.bit_buf & 0xFF
                    if self.is_inverted:
                        current_byte ^= 0xFF
                    self.byte_buf += bytes([current_byte])
                    
                    # Interleaving Depth: We must collect a fixed block because 
                    # the length byte itself is shuffled inside the matrix.
                    # We'll collect 120 bytes (maximum expected frame size).
                    target_len = 120 if self.use_interleaving else (2 + self.fec_payload_len + 2)

                    # Peek only if NOT interleaved
                    if not self.use_interleaving and len(self.byte_buf) == 2:
                        data_peek = self.dewhiten(self.byte_buf) if self.use_whitening else self.byte_buf
                        msg_type, plen = struct.unpack('BB', data_peek)
                        if plen > 128: self.state = "SEARCH"; continue
                        self.fec_payload_len = ((plen + 10) // 11) * 15 if self.use_fec else plen

                    if len(self.byte_buf) >= target_len:
                        raw_data = self.dewhiten(self.byte_buf) if self.use_whitening else self.byte_buf
                        
                        if self.use_interleaving:
                            data = self.interleaver.deinterleave(raw_data, len(raw_data))
                        else:
                            data = raw_data
                        
                        # Now parse the header from de-interleaved data
                        msg_type, plen = struct.unpack('BB', data[:2])
                        fec_len = ((plen + 10) // 11) * 15 if self.use_fec else plen
                        
                        # Verify Packet: Type(1) + Len(1) + FEC_Payload + CRC(2)
                        total_pkt_len = 2 + fec_len + 2
                        if total_pkt_len <= len(data):
                            actual_packet = data[:total_pkt_len]
                            calc_crc = self.crc16_ccitt(actual_packet[:-2])
                            received_crc = struct.unpack('>H', actual_packet[-2:])[0]
                            
                            if calc_crc == received_crc:
                                print(f"[Depacketizer] CRC PASSED! Type: {msg_type}, Len: {plen}")
                                fec_payload = actual_packet[2:-2]
                                
                                if self.use_fec:
                                    decoded = b''
                                    for j in range(0, len(fec_payload), 15):
                                        chunk = fec_payload[j:j+15]
                                        nib = []
                                        for b in chunk: nib.extend([(b >> 4) & 0x0F, b & 0x0F])
                                        block1 = self.rs.decode(nib[:15])
                                        block2 = self.rs.decode(nib[15:])
                                        all_nib = block1 + block2
                                        for k in range(0, 22, 2):
                                            decoded += bytes([(all_nib[k] << 4) | all_nib[k+1]])
                                    payload = decoded[:plen]
                                    if payload != actual_packet[2:2+plen]:
                                        print("[Depacketizer] FEC REPAIR SUCCESSFUL.")
                                else:
                                    payload = fec_payload
                                
                                meta = pmt.make_dict()
                                meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(msg_type))
                                self.message_port_pub(pmt.intern("out"), pmt.cons(meta, pmt.init_u8vector(len(payload), list(payload))))
                            else:
                                # For debug
                                # print(f"[Depacketizer] CRC FAILED: 0x{calc_crc:04X} vs 0x{received_crc:04X}")
                                pass
                        
                        self.state = "SEARCH"

        self.consume(0, len(in0))
        return 0
