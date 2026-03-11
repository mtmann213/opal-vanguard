#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Performance-Grade Packetizer (v19.0 GOLD)

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
        l_cfg = self.cfg.get('link_layer', {})
        p_cfg = self.cfg.get('physical', {})
        self.frame_size = l_cfg.get('frame_size', 120)
        self.preamble_len = p_cfg.get('preamble_len', 512)
        self.use_fec = l_cfg.get('use_fec', True)
        self.use_interleaving = l_cfg.get('use_interleaving', True)
        self.use_whitening = l_cfg.get('use_whitening', True)
        self.use_nrzi = l_cfg.get('use_nrzi', True)
        self.fec_mode = self.cfg.get('mission', {}).get('id', "")
        
        # Security State
        self.use_comsec = l_cfg.get('use_comsec', False)
        self.use_transec = l_cfg.get('use_transec', False)
        self.use_anti_replay = l_cfg.get('use_anti_replay', False)
        self.comsec_key = bytes.fromhex(l_cfg.get('comsec_key', '00'*32)) if self.use_comsec else None
        self.replay_counter = 0
        
        # Initialize DSP Helpers
        self.interleaver = MatrixInterleaver(rows=16)
        self.scrambler = Scrambler(mask=0x48, seed=0x7F)
        self.nrzi = NRZIEncoder()
        self.ccsk = CCSKProcessor()
        self.use_ccsk = (self.cfg.get('dsss', {}).get('enabled', False) and self.cfg.get('dsss', {}).get('type') == "CCSK")
        
        if self.use_fec:
            from rs_helper import RS1511
            self.rs = RS1511()

        self.message_port_register_in(pmt.intern("in"))
        self.message_port_register_out(pmt.intern("out"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)

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
        raw_payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        # Standardize payload to frame_size
        payload = raw_payload.ljust(self.frame_size, b'\x00')[:self.frame_size]
        
        m_type, seq = 0, 0
        if pmt.is_dict(pmt.car(msg)):
            seq = pmt.to_long(pmt.dict_ref(pmt.car(msg), pmt.intern("seq"), pmt.from_long(0)))
            m_type = pmt.to_long(pmt.dict_ref(pmt.car(msg), pmt.intern("type"), pmt.from_long(0)))

        # Header Construction
        # Ensure plen does not exceed frame_size
        actual_plen = min(len(raw_payload), self.frame_size)
        
        if self.use_transec:
            self.replay_counter = (self.replay_counter + 1) & 0xFFFFFFFF
            idx = self.replay_counter if self.use_anti_replay else seq
            header = struct.pack('<BBI B', self.src_id, m_type, idx, actual_plen)
            crc = self.calculate_crc16(header + payload)
            block = header + payload + struct.pack('>H', crc)
            nonce = os.urandom(16)
            cipher = Cipher(algorithms.AES(self.comsec_key), modes.CTR(nonce), backend=default_backend())
            raw_block = nonce + cipher.encryptor().update(block) + cipher.encryptor().finalize()
        else:
            final_payload = payload
            if self.use_comsec and self.comsec_key and m_type == 0:
                nonce = os.urandom(16)
                cipher = Cipher(algorithms.AES(self.comsec_key), modes.CTR(nonce), backend=default_backend())
                final_payload = nonce + cipher.encryptor().update(payload) + cipher.encryptor().finalize()
            header = struct.pack('BBBB', self.src_id, m_type, seq, actual_plen)
            crc = self.calculate_crc16(header + final_payload)
            raw_block = header + final_payload + struct.pack('>H', crc)

        # 3. RS-FEC Encoding
        data_block = raw_block
        if self.use_fec:
            fec_payload = b''
            k, n = self.rs.K, self.rs.N
            for i in range(0, len(raw_block), k):
                chunk = raw_block[i:i+k].ljust(k, b'\x00')
                nibs = []
                for b in chunk: nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
                # Encode both halves
                all_e = self.rs.encode(nibs[:k]) + self.rs.encode(nibs[k:])
                # Sequentially pack nibbles back into bytes
                for m in range(0, 2*n, 2):
                    fec_payload += bytes([( ((all_e[m]&0x0F) << 4) | (all_e[m+1]&0x0F) )])
            data_block = fec_payload

        # Final Formatting
        packet = self.interleaver.interleave(data_block)
        if self.use_whitening: self.scrambler.reset(); packet = self.scrambler.process(packet)

        # Modulation
        bits = np.unpackbits(np.frombuffer(packet, dtype=np.uint8), bitorder='big').tolist()
        is_tactical = ("LEVEL_6" in self.fec_mode or "LEVEL_7" in self.fec_mode or "LEVEL_8" in self.fec_mode)
        
        if self.use_nrzi and not is_tactical:
            self.nrzi.tx_state = 0
            bits = self.nrzi.encode(bits)
        
        final_bits = bits
        if self.use_ccsk:
            bits_arr = np.array(bits, dtype=np.uint8)
            if len(bits_arr) % 5: bits_arr = np.append(bits_arr, np.zeros(5 - (len(bits_arr) % 5), dtype=np.uint8))
            syms = np.packbits(bits_arr.reshape(-1, 5), axis=1, bitorder='big') >> 3
            final_bits = self.ccsk.vectorized_encode(syms.flatten())

        preamble = ([1,0]*(self.preamble_len // 2))[:self.preamble_len]
        sync_val = 0x3D4C5B6AACE12345 if is_tactical else 0x3D4C5B6A
        sync_len = 64 if is_tactical else 32
        syncword = [(sync_val >> i) & 1 for i in range(sync_len-1, -1, -1)]
        out_bits = preamble + syncword + final_bits
        
        # v19.20: SANITIZE METADATA. Use a brand new dictionary to kill any stray rx_time tags.
        # Note: tx_sob/tx_eob are omitted as they are handled automatically by the USRP Sink via packet_len.
        clean_meta = pmt.make_dict()
        clean_meta = pmt.dict_add(clean_meta, pmt.intern("packet_len"), pmt.from_long(len(out_bits)))
        
        self.message_port_pub(pmt.intern("out"), pmt.cons(clean_meta, pmt.init_u8vector(len(out_bits), out_bits)))

    def work(self, i, o): return 0
