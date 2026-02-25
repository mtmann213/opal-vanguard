#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Depacketizer Block (DSSS + Config Support)

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

class depacketizer(gr.basic_block):
    def __init__(self, config_path="config.yaml"):
        gr.basic_block.__init__(self, name="depacketizer", in_sig=[np.uint8], out_sig=None)
        
        # Load Config
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
            
        self.use_fec = self.cfg['link_layer']['use_fec']
        self.use_whitening = self.cfg['link_layer']['use_whitening']
        self.use_interleaving = self.cfg['link_layer']['use_interleaving']
        self.use_dsss = self.cfg['link_layer']['use_dsss']
        self.sf = self.cfg['dsss']['spreading_factor']
        
        self.rs = RS1511()
        self.interleaver = MatrixInterleaver(rows=8)
        self.dsss = DSSSProcessor(chipping_code=self.cfg['dsss']['chipping_code'])
        
        self.message_port_register_out(pmt.intern("out"))
        
        self.state = "SEARCH"
        self.syncword_bits = 0x3D4C5B6A
        self.bit_buf = 0
        self.bits_in_buf = 0
        self.byte_buf = b''
        self.chip_buf = []

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
                    print(f"[Depacketizer] Syncword Found! (DSSS: {self.use_dsss})")
                    self.state = "COLLECT"
                    self.byte_buf = b''
                    self.chip_buf = []
                    self.bits_in_buf = 0
                    
            elif self.state == "COLLECT":
                # If using DSSS, we collect chips and de-spread them into bytes
                if self.use_dsss:
                    # Map 0/1 bits from demod to -1/1 chips for correlation
                    chip = 1 if bit == 1 else -1
                    if self.is_inverted: chip *= -1
                    self.chip_buf.append(chip)
                    
                    if len(self.chip_buf) == self.sf:
                        # De-spread one bit
                        recovered_bit = self.dsss.despread(self.chip_buf)[0]
                        self.chip_buf = []
                        
                        # Pack bit into byte_buf
                        self.bits_in_buf += 1
                        self.bit_buf = (self.bit_buf << 1) | recovered_bit
                        
                        if self.bits_in_buf % 8 == 0:
                            self.byte_buf += bytes([self.bit_buf & 0xFF])
                else:
                    # Normal bit collection
                    self.bits_in_buf += 1
                    if self.bits_in_buf % 8 == 0:
                        current_byte = self.bit_buf & 0xFF
                        if self.is_inverted: current_byte ^= 0xFF
                        self.byte_buf += bytes([current_byte])

                # Check if we have a full block
                # Interleaving requires a fixed block (120 bytes)
                target_len = 120 if self.use_interleaving else 64 # Larger default if no interleaving
                
                if len(self.byte_buf) >= target_len:
                    raw_data = self.dewhiten(self.byte_buf) if self.use_whitening else self.byte_buf
                    
                    if self.use_interleaving:
                        data = self.interleaver.deinterleave(raw_data, len(raw_data))
                    else:
                        data = raw_data
                    
                    msg_type, plen = struct.unpack('BB', data[:2])
                    fec_len = ((plen + 10) // 11) * 15 if self.use_fec else plen
                    
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
                    
                    self.state = "SEARCH"

        self.consume(0, len(in0))
        return 0
