#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Mission-Controlled Packetizer (True Signal Build v7.6)

import numpy as np
from gnuradio import gr
import pmt
import struct
import os
import sys
import yaml

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from rs_helper import RS1511, RS3115
from dsp_helper import MatrixInterleaver, DSSSProcessor, NRZIEncoder, ManchesterEncoder, Scrambler, CCSKProcessor

class packetizer(gr.basic_block):
    def __init__(self, config_path="mission_configs/level1_soft_link.yaml", src_id=0):
        gr.basic_block.__init__(self, name="packetizer", in_sig=None, out_sig=None)
        self.src_id = src_id
        with open(config_path, 'r') as f: self.cfg = yaml.safe_load(f)
        l_cfg = self.cfg['link_layer']
        self.rows = l_cfg.get('interleaver_rows', 8)
        self.use_fec = l_cfg.get('use_fec', True)
        self.use_interleaving = l_cfg.get('use_interleaving', True)
        self.use_whitening = l_cfg.get('use_whitening', True)
        self.use_nrzi = l_cfg.get('use_nrzi', True)
        self.use_manchester = l_cfg.get('use_manchester', False)
        self.fec_mode = self.cfg.get('mission', {}).get('id', "")
        
        self.interleaver = MatrixInterleaver(rows=self.rows)
        self.scrambler = Scrambler(mask=l_cfg.get('scrambler_mask', 0x48), seed=l_cfg.get('scrambler_seed', 0x7F))
        self.nrzi = NRZIEncoder()
        self.manchester = ManchesterEncoder()
        self.ccsk = CCSKProcessor()
        self.rs3115 = RS3115()
        self.rs1511 = RS1511()
        
        self.use_dsss = self.cfg['dsss'].get('enabled', False)
        self.dsss_type = self.cfg['dsss'].get('type', "DSSS")
        self.sf = self.cfg['dsss'].get('spreading_factor', 31)
        self.dsss = DSSSProcessor(chipping_code=self.cfg['dsss'].get('chipping_code', [1,-1]))

        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)
        self.message_port_register_out(pmt.intern("out"))

    def handle_msg(self, msg):
        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        m_type, seq = 0, 0
        if pmt.is_dict(pmt.car(msg)):
            seq = pmt.to_long(pmt.dict_ref(pmt.car(msg), pmt.intern("seq"), pmt.from_long(0)))
            m_type = pmt.to_long(pmt.dict_ref(pmt.car(msg), pmt.intern("type"), pmt.from_long(0)))

        # 1. FEC
        if self.use_fec:
            if "LINK-16" in self.fec_mode or "LEVEL_6" in self.fec_mode:
                p_bits = []
                for b in payload: [p_bits.append((b >> (7-i)) & 1) for i in range(8)]
                while len(p_bits) % 75 != 0: p_bits.extend([0]*5)
                f_bits = []
                for j in range(0, len(p_bits), 75):
                    syms = [int(''.join(map(str, p_bits[j+k*5:j+k*5+5])), 2) for k in range(15)]
                    encoded = self.rs3115.encode(syms)
                    for s in encoded: [f_bits.append((s >> (4-k)) & 1) for k in range(5)]
                f_bytes = []; acc, bc = 0, 0
                for b in f_bits:
                    acc = (acc << 1) | b; bc += 1
                    if bc == 8: f_bytes.append(acc); acc, bc = 0, 0
                if bc > 0: f_bytes.append(acc << (8-bc))
                fec_payload = bytes(f_bytes)
            else:
                fec_payload = b''
                for i in range(0, len(payload), 11):
                    chunk = payload[i:i+11].ljust(11, b'\x00'); nibs = []
                    for b in chunk: nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
                    e1 = self.rs1511.encode(nibs[:11]); e2 = self.rs1511.encode(nibs[11:])
                    all_e = e1 + e2
                    for k in range(0, 30, 2): fec_payload += bytes([(all_e[k] << 4) | all_e[k+1]])
        else: fec_payload = payload

        # 2. Header & CRC
        header = struct.pack('BBBB', self.src_id, m_type, seq, len(payload))
        packet = header + fec_payload
        crc = 0xFFFF
        for byte in packet:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                else: crc = (crc << 1)
                crc &= 0xFFFF
        packet += struct.pack('>H', crc)

        # 3. Padding & DSP
        target_bytes = 320 if "LINK-16" in self.fec_mode or "LEVEL_6" in self.fec_mode else 120
        packet = packet.ljust(target_bytes, b'\x00')[:target_bytes]
        if self.use_interleaving: packet = self.interleaver.interleave(packet, len(packet))
        if self.use_whitening: self.scrambler.reset(); packet = self.scrambler.process(packet)
            
        # 4. Bit-Level Processing (Output UNPACKED BITS for GNU Radio Modulators)
        bits = []
        for b in packet: [bits.append((b >> (7-i)) & 1) for i in range(8)]
        
        if self.use_nrzi: self.nrzi.tx_state = 0; bits = self.nrzi.encode(bits)
        if self.use_manchester: bits = self.manchester.encode(bits)
        
        # 5. Spreading
        final_bits = []
        if self.use_dsss:
            if self.dsss_type == "CCSK":
                for i in range(0, len(bits), 5):
                    sym = 0
                    for j in range(5): sym = (sym << 1) | bits[i+j]
                    final_bits.extend(self.ccsk.encode_symbol(sym))
            else:
                for b in bits: final_bits.extend(self.dsss.encode([b]))
        else: final_bits = bits
        
        # 6. Framing (Preamble + Syncword + Data)
        preamble = [1,0]*16 # 0xAAAA
        syncword = [int(b) for b in format(0x3D4C5B6A, '032b')]
        out_bits = preamble + syncword + final_bits
        
        # Output as UNPACKED bits (one bit per byte)
        self.message_port_pub(pmt.intern("out"), pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(out_bits), out_bits)))

    def work(self, i, o): return 0
