#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Performance-Grade Packetizer (v16.1.0 Standard-Pivot)

import numpy as np
from gnuradio import gr
import pmt
import struct
import os
import yaml
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from dsp_helper import MatrixInterleaver, Scrambler, NRZIEncoder, CCSKProcessor

class packetizer(gr.basic_block):
    def __init__(self, config_path="mission_configs/level1_soft_link.yaml", src_id=0):
        gr.basic_block.__init__(self, name="packetizer", in_sig=None, out_sig=None)
        self.src_id = src_id
        with open(config_path, 'r') as f: self.cfg = yaml.safe_load(f)
        l_cfg, p_cfg = self.cfg.get('link_layer', {}), self.cfg.get('physical', {})
        self.frame_size, self.use_fec = l_cfg.get('frame_size', 120), l_cfg.get('use_fec', True)
        self.use_interleaving, self.use_whitening = l_cfg.get('use_interleaving', True), l_cfg.get('use_whitening', True)
        self.use_nrzi, self.fec_mode = l_cfg.get('use_nrzi', True), self.cfg.get('mission', {}).get('id', "")
        self.preamble_len = p_cfg.get('preamble_len', 1024); self.sync_hex = p_cfg.get('syncword', "0x3D4C5B6A")
        self.use_comsec = l_cfg.get('use_comsec', False)
        self.comsec_key = bytes.fromhex(l_cfg.get('comsec_key', '00'*32)) if self.use_comsec else None
        self.interleaver = MatrixInterleaver(rows=l_cfg.get('interleaver_rows', 15))
        self.scrambler = Scrambler(mask=l_cfg.get('scrambler_mask', 0x48), seed=l_cfg.get('scrambler_seed', 0x7F))
        self.nrzi, self.ccsk = NRZIEncoder(), CCSKProcessor()
        self.use_ccsk = (self.cfg.get('dsss', {}).get('enabled', False) and self.cfg.get('dsss', {}).get('type') == "CCSK")
        if self.use_fec:
            from rs_helper import RS1511
            self.rs = RS1511()
        self.message_port_register_in(pmt.intern("in")); self.message_port_register_out(pmt.intern("out")); self.set_msg_handler(pmt.intern("in"), self.handle_msg)

    def calculate_crc16(self, data):
        crc = 0xFFFF
        for byte in data:
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                else: crc <<= 1
            crc &= 0xFFFF
        return crc

    def handle_msg(self, msg):
        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        m_type, seq = 0, 0
        if pmt.is_dict(pmt.car(msg)):
            seq = pmt.to_long(pmt.dict_ref(pmt.car(msg), pmt.intern("seq"), pmt.from_long(0)))
            m_type = pmt.to_long(pmt.dict_ref(pmt.car(msg), pmt.intern("type"), pmt.from_long(0)))
        if self.use_comsec and self.comsec_key and m_type == 0:
            nonce = os.urandom(16); cipher = Cipher(algorithms.AES(self.comsec_key), modes.CTR(nonce), backend=default_backend()); payload = nonce + cipher.encryptor().update(payload) + cipher.encryptor().finalize()
        header = struct.pack('BBBB', self.src_id, m_type, seq, len(payload))
        raw_block = header + payload + struct.pack('>H', self.calculate_crc16(header + payload))
        data_block = raw_block
        if self.use_fec:
            fec_payload = b''
            for i in range(0, len(raw_block), 11):
                chunk = raw_block[i:i+11].ljust(11, b'\x00'); nibs = []
                for b in chunk: nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
                all_e = self.rs.encode(nibs[:11]) + self.rs.encode(nibs[11:])
                for k in range(0, 30, 2): fec_payload += bytes([( (all_e[k] << 4) | all_e[k+1] )])
            data_block = fec_payload
        packet = data_block.ljust(self.frame_size, b'\x00')[:self.frame_size]
        if self.use_interleaving: packet = self.interleaver.interleave(packet)
        if self.use_whitening: self.scrambler.reset(); packet = self.scrambler.process(packet)
        bits = []
        for b in packet:
            for j in range(8): bits.append((b >> (7-j)) & 1)
        f_id = str(self.fec_mode).upper()
        if self.use_nrzi and not ("LINK16" in f_id or "LINK-16" in f_id or "LEVEL_6" in f_id or "LEVEL_7" in f_id): self.nrzi.tx_state = 0; bits = self.nrzi.encode(bits)
        final_bits = bits
        if self.use_ccsk:
            final_bits = []
            for i in range(0, len(bits), 5):
                chunk = bits[i:i+5]; sym = 0
                for b in chunk: sym = (sym << 1) | b
                final_bits.extend(self.ccsk.encode_symbol(sym))
        preamble = ([1,0]*(self.preamble_len // 2))[:self.preamble_len]; sync_val = int(self.sync_hex, 16); syncword = [int(b) for b in format(sync_val, f'0{(len(self.sync_hex)-2)*4}b')]
        # v16.1.0: Always emit bits. Hardware acceleration handles sample-conversion.
        out_bits = preamble + syncword + final_bits + ([0]*2048)
        self.message_port_pub(pmt.intern("out"), pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(out_bits), out_bits)))
    def work(self, i, o): return 0
