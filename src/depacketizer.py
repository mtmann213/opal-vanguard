#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Mission-Controlled Depacketizer (Advanced Diagnostics)

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

class depacketizer(gr.basic_block):
    def __init__(self, config_path="config.yaml"):
        gr.basic_block.__init__(self, name="depacketizer", in_sig=[np.uint8], out_sig=None)
        
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
        self.sf = self.cfg['dsss'].get('spreading_factor', 31)
        
        # Components
        self.rs = RS1511()
        self.interleaver = MatrixInterleaver(rows=l_cfg.get('interleaver_rows', 8))
        self.scrambler = Scrambler(mask=l_cfg.get('scrambler_mask', 0x48), seed=l_cfg.get('scrambler_seed', 0x7F))
        self.manchester = ManchesterEncoder()
        self.nrzi = NRZIEncoder()
        self.dsss = DSSSProcessor(chipping_code=self.cfg['dsss']['chipping_code'])
        
        self.message_port_register_out(pmt.intern("out"))
        self.message_port_register_out(pmt.intern("diagnostics"))
        
        self.state = "SEARCH"
        self.syncword_bits = 0x3D4C5B6A
        self.bit_buf = 0
        self.recovered_bits = []
        self.active_pkt_len = 0
        
        # Metrics tracking
        self.correlation_sum = 0
        self.bits_processed = 0

    def verify_crc(self, data):
        if self.crc_type == "NONE": return True, 0, 0
        if self.crc_type == "CRC16":
            if len(data) < 2: return False, 0, 0
            payload, received_crc = data[:-2], struct.unpack('>H', data[-2:])[0]
            crc = 0xFFFF
            for byte in payload:
                crc ^= byte << 8
                for _ in range(8):
                    if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                    else: crc = (crc << 1)
                    crc &= 0xFFFF
            return crc == received_crc, crc, received_crc
        elif self.crc_type == "CRC32":
            if len(data) < 4: return False, 0, 0
            payload, received_crc = data[:-4], struct.unpack('>I', data[-4:])[0]
            calc_crc = binascii.crc32(payload) & 0xFFFFFFFF
            return calc_crc == received_crc, calc_crc, received_crc
        return False, 0, 0

    def general_work(self, input_items, output_items):
        in0 = input_items[0]
        for i in range(len(in0)):
            bit = int(in0[i]) & 1
            
            if self.state == "SEARCH":
                self.bit_buf = ((self.bit_buf << 1) | bit) & 0xFFFFFFFF
                if self.bit_buf == self.syncword_bits or self.bit_buf == (0xFFFFFFFF ^ self.syncword_bits):
                    self.is_inverted = (self.bit_buf == (0xFFFFFFFF ^ self.syncword_bits))
                    self.state = "COLLECT"
                    self.recovered_bits = []
                    self.nrzi.reset()
                    if self.is_inverted: self.nrzi.rx_state = 1
                    self.chip_buf = []
                    self.active_pkt_len = 0
                    self.correlation_sum = 0
                    self.bits_processed = 0
                    continue 
                    
            elif self.state == "COLLECT":
                if self.use_dsss:
                    chip = 1 if bit == 1 else -1
                    if self.is_inverted: chip *= -1
                    self.chip_buf.append(chip)
                    if len(self.chip_buf) == self.sf:
                        # Modified DSSS despread to return correlation magnitude
                        chunk = np.array(self.chip_buf)
                        corr = np.sum(chunk * self.dsss.code)
                        self.correlation_sum += abs(corr)
                        self.bits_processed += 1
                        
                        recovered_bit = 1 if corr > 0 else 0
                        self.chip_buf = []
                        self.recovered_bits.append(recovered_bit)
                else:
                    self.recovered_bits.append(bit ^ (1 if self.is_inverted else 0))

                # Header Peek for length
                if not self.use_interleaving and self.active_pkt_len == 0:
                    needed_bits = 16 * (2 if self.use_manchester else 1)
                    if len(self.recovered_bits) >= needed_bits:
                        header_bits = self.recovered_bits[:needed_bits]
                        if self.use_manchester: header_bits = self.manchester.decode(header_bits)
                        temp_nrzi = NRZIEncoder(); temp_nrzi.rx_state = 1 if self.is_inverted else 0
                        if self.use_nrzi: header_bits = temp_nrzi.decode(header_bits)
                        
                        acc = 0; h_bytes = []
                        for j, b in enumerate(header_bits):
                            acc = (acc << 1) | b
                            if (j + 1) % 8 == 0: h_bytes.append(acc); acc = 0
                        h_data = bytes(h_bytes)
                        if self.use_whitening: h_data = self.scrambler.process(h_data)
                        
                        try:
                            m_type, plen = struct.unpack('BB', h_data)
                            f_len = ((plen + 10) // 11) * 15 if self.use_fec else plen
                            c_len = 4 if self.crc_type == "CRC32" else (2 if self.crc_type == "CRC16" else 0)
                            self.active_pkt_len = 2 + f_len + c_len
                        except: self.state = "SEARCH"; continue

                target_bytes = 120 if self.use_interleaving else self.active_pkt_len
                target_bits = target_bytes * 8 if target_bytes > 0 else 2048
                if self.use_manchester: target_bits *= 2
                
                if len(self.recovered_bits) >= target_bits:
                    bits = self.recovered_bits[:target_bits]
                    if self.use_manchester: self.manchester.reset(); bits = self.manchester.decode(bits)
                    if self.use_nrzi: bits = self.nrzi.decode(bits)
                    
                    byte_list = []
                    acc = 0
                    for j, b in enumerate(bits):
                        acc = (acc << 1) | b
                        if (j + 1) % 8 == 0: byte_list.append(acc); acc = 0
                    data_block = bytes(byte_list)
                    
                    if self.use_whitening: data_block = self.scrambler.process(data_block)
                    if self.use_interleaving: data_block = self.interleaver.deinterleave(data_block, len(data_block))
                    
                    try:
                        msg_type, plen = struct.unpack('BB', data_block[:2])
                        f_len = ((plen + 10) // 11) * 15 if self.use_fec else plen
                        c_len = 4 if self.crc_type == "CRC32" else (2 if self.crc_type == "CRC16" else 0)
                        
                        actual_packet = data_block[:2 + f_len + c_len]
                        crc_ok, _, _ = self.verify_crc(actual_packet)
                        
                        # --- Dashboard Calculation ---
                        # 1. Signal Confidence (DSSS Correlation)
                        conf = 100.0
                        if self.use_dsss and self.bits_processed > 0:
                            avg_corr = self.correlation_sum / self.bits_processed
                            conf = (avg_corr / self.sf) * 100.0
                        
                        # 2. FEC Repair Stats
                        total_symbols = 0; corrected = 0
                        if crc_ok:
                            fec_payload = actual_packet[2 : 2+f_len]
                            if self.use_fec:
                                decoded = b''
                                for j in range(0, len(fec_payload), 15):
                                    chunk_nibs = []
                                    for b in fec_payload[j:j+15]: chunk_nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
                                    b1_dec = self.rs.decode(chunk_nibs[:15]); b2_dec = self.rs.decode(chunk_nibs[15:])
                                    total_symbols += 30
                                    if b1_dec != chunk_nibs[:11]: corrected += 1
                                    if b2_dec != chunk_nibs[15:15+11]: corrected += 1
                                    all_nibs = b1_dec + b2_dec
                                    for k in range(0, 22, 2): decoded += bytes([(all_nibs[k] << 4) | all_nibs[k+1]])
                                payload = decoded[:plen]
                            else: payload = fec_payload
                            
                            # Terminal Dashboard Output
                            status_str = "\033[92m[OK]\033[0m" if corrected == 0 else f"\033[93m[FIXED {corrected}]\033[0m"
                            print(f"{status_str} Type: {msg_type} | Len: {plen:<2} | Conf: {conf:5.1f}% | RX: {payload}")
                            sys.stdout.flush()
                            
                            self.message_port_pub(pmt.intern("out"), pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(payload), list(payload))))
                        else:
                            print(f"\033[91m[FAIL]\033[0m {self.crc_type} Error | Conf: {conf:5.1f}%")
                            sys.stdout.flush()
                    except Exception as e: pass
                    
                    self.state = "SEARCH"; self.bit_buf = 0 

        self.consume(0, len(in0))
        return 0
