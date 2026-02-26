#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Mission-Controlled Depacketizer (with Diagnostics)

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
        return False, 0, 0

    def general_work(self, input_items, output_items):
        in0 = input_items[0]
        for i in range(len(in0)):
            bit = int(in0[i]) & 1
            self.bit_buf = ((self.bit_buf << 1) | bit) & 0xFFFFFFFF
            
            if self.state == "SEARCH":
                if self.bit_buf == self.syncword_bits or self.bit_buf == (0xFFFFFFFF ^ self.syncword_bits):
                    self.is_inverted = (self.bit_buf == (0xFFFFFFFF ^ self.syncword_bits))
                    print(f"[Depacketizer] Syncword Found! (DSSS: {self.use_dsss}, NRZI: {self.use_nrzi})")
                    sys.stdout.flush()
                    self.state = "COLLECT"
                    self.recovered_bits = []
                    self.nrzi.rx_state = 1 if self.is_inverted else 0
                    self.chip_buf = []
                    
            elif self.state == "COLLECT":
                if self.use_dsss:
                    chip = 1 if bit == 1 else -1
                    if self.is_inverted: chip *= -1
                    self.chip_buf.append(chip)
                    if len(self.chip_buf) == self.sf:
                        self.recovered_bits.append(self.dsss.despread(self.chip_buf)[0])
                        self.chip_buf = []
                else:
                    self.recovered_bits.append(bit ^ (1 if self.is_inverted else 0))

                target_bytes = 120 if self.use_interleaving else 64
                target_bits = target_bytes * 8
                if self.use_manchester: target_bits *= 2
                
                if len(self.recovered_bits) >= target_bits:
                    bits = self.recovered_bits[:target_bits]
                    if self.use_manchester: bits = self.manchester.decode(bits)
                    if self.use_nrzi: bits = self.nrzi.decode(bits)
                    
                    byte_list = []
                    acc = 0
                    for j, b in enumerate(bits):
                        acc = (acc << 1) | b
                        if (j + 1) % 8 == 0:
                            byte_list.append(acc); acc = 0
                    data_block = bytes(byte_list)
                    
                    if self.use_whitening: data_block = self.scrambler.process(data_block)
                    if self.use_interleaving: data_block = self.interleaver.deinterleave(data_block, len(data_block))
                    
                    msg_type, plen = struct.unpack('BB', data_block[:2])
                    fec_len = ((plen + 10) // 11) * 15 if self.use_fec else plen
                    crc_len = 2 # Hardcoded for now
                    
                    actual_packet = data_block[:2 + fec_len + crc_len]
                    crc_ok, calc_crc, recv_crc = self.verify_crc(actual_packet)
                    
                    # --- Diagnostics ---
                    diag = pmt.make_dict()
                    diag = pmt.dict_add(diag, pmt.intern("crc_ok"), pmt.from_bool(crc_ok))
                    diag = pmt.dict_add(diag, pmt.intern("inverted"), pmt.from_bool(self.is_inverted))
                    diag = pmt.dict_add(diag, pmt.intern("msg_type"), pmt.from_long(msg_type))
                    
                    if crc_ok:
                        print(f"[Depacketizer] {self.crc_type} PASSED! Type: {msg_type}, Len: {plen}")
                        fec_payload = actual_packet[2 : 2+fec_len]
                        corrected_symbols = 0
                        if self.use_fec:
                            decoded = b''
                            for j in range(0, len(fec_payload), 15):
                                chunk = fec_payload[j:j+15]
                                nib = []
                                for b in chunk: nib.extend([(b >> 4) & 0x0F, b & 0x0F])
                                b1 = self.rs.decode(nib[:15]); b2 = self.rs.decode(nib[15:])
                                if b1 != nib[:11]: corrected_symbols += 1
                                if b2 != nib[15:15+11]: corrected_symbols += 1
                                for k in range(0, 22, 2): decoded += bytes([(b1[k] << 4) | b1[k+1]])
                            payload = decoded[:plen]
                        else:
                            payload = fec_payload
                        
                        if corrected_symbols > 0:
                            print(f"[Depacketizer] FEC Corrected {corrected_symbols} blocks.")
                        
                        print(f"[Depacketizer] RECOVERED: {payload}")
                        sys.stdout.flush()
                        
                        diag = pmt.dict_add(diag, pmt.intern("fec_corrections"), pmt.from_long(corrected_symbols))
                        self.message_port_pub(pmt.intern("diagnostics"), diag)
                        self.message_port_pub(pmt.intern("out"), pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(payload), list(payload))))
                    else:
                        print(f"[Depacketizer] {self.crc_type} FAILED: Calc 0x{calc_crc:04X} != Recv 0x{recv_crc:04X}")
                        sys.stdout.flush()
                        self.message_port_pub(pmt.intern("diagnostics"), diag)
                    
                    self.state = "SEARCH"

        self.consume(0, len(in0))
        return 0
