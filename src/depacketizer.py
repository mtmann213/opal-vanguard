#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - High-Performance Depacketizer (v19.0 GOLD)

import numpy as np
from gnuradio import gr
import pmt
import struct
import os
import yaml
import time
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from dsp_helper import MatrixInterleaver, Scrambler, NRZIEncoder, CCSKProcessor

class depacketizer(gr.basic_block):
    def __init__(self, config_path="mission_configs/level1_soft_link.yaml", src_id=0, ignore_self=False):
        gr.basic_block.__init__(self, name="depacketizer", in_sig=[np.uint8], out_sig=None)
        self.src_id, self.ignore_self = src_id, ignore_self
        
        with open(config_path, 'r') as f: self.cfg = yaml.safe_load(f)
        l_cfg = self.cfg.get('link_layer', {})
        self.frame_size = l_cfg.get('frame_size', 120)
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
        self.last_indices = {} 
        
        # Initialize DSP Helpers
        self.interleaver = MatrixInterleaver(rows=16)
        self.scrambler = Scrambler(mask=0x48, seed=0x7F)
        self.nrzi = NRZIEncoder()
        self.ccsk = CCSKProcessor()
        self.use_ccsk = (self.cfg.get('dsss', {}).get('enabled', False) and self.cfg.get('dsss', {}).get('type') == "CCSK")
        
        if self.use_fec:
            from rs_helper import RS1511
            self.rs = RS1511()

        self.message_port_register_out(pmt.intern("out"))
        self.message_port_register_out(pmt.intern("diagnostics"))
        self.message_port_register_in(pmt.intern("pdu_in"))
        self.set_msg_handler(pmt.intern("pdu_in"), self.handle_pdu)
        
        self.state = "SEARCH"
        self.bit_buf = 0
        self.recovered_bits = []
        self.ccsk_buf = []
        self.is_inverted = False
        
        self.sync_val_32 = 0x3D4C5B6A
        self.sync_val_64 = 0x3D4C5B6AACE12345

    def verify_crc(self, payload, true_plen, sid, m_type, seq):
        if len(payload) < (true_plen + 2): return False
        extracted_crc = struct.unpack('>H', payload[true_plen:true_plen+2])[0]
        crc = 0xFFFF
        header_base = struct.pack('BBBB', sid, m_type, seq, true_plen)
        for byte in (header_base + payload[:true_plen]):
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                else: crc <<= 1
            crc &= 0xFFFF
        return crc == extracted_crc

    def verify_crc_hardened(self, block_data, extracted_crc_bytes):
        if len(extracted_crc_bytes) < 2: return False
        target_crc = struct.unpack('>H', extracted_crc_bytes)[0]
        crc = 0xFFFF
        for byte in block_data:
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                else: crc <<= 1
            crc &= 0xFFFF
        return crc == target_crc

    def handle_pdu(self, msg):
        data_block = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        self.process_recovered_block(data_block, 1.0)

    def process_recovered_block(self, data_block, confidence):
        try:
            # 1. Un-Formatting
            if self.use_whitening: self.scrambler.reset(); data_block = self.scrambler.process(data_block)
            data_block = self.interleaver.deinterleave(data_block)
            
            # 2. FEC
            processed_block = data_block
            repairs_made = 0
            if self.use_fec:
                healed = b''
                k, n = self.rs.K, self.rs.N
                for j in range(0, len(data_block), n):
                    chunk = data_block[j:j+n]
                    if len(chunk) < n: break
                    nibs = []
                    for b in chunk: nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
                    dn1, e1 = self.rs.decode(nibs[:n])
                    dn2, e2 = self.rs.decode(nibs[n:])
                    repairs_made += (e1 + e2)
                    combined = dn1 + dn2
                    for m in range(0, 2*k, 2): healed += bytes([( (combined[m] << 4) | combined[m+1] )])
                processed_block = healed

            # 3. Decryption & Integrity
            if self.use_transec:
                if len(processed_block) < 16: return
                nonce, ct = processed_block[:16], processed_block[16:]
                cipher = Cipher(algorithms.AES(self.comsec_key), modes.CTR(nonce), backend=default_backend())
                block = cipher.decryptor().update(ct) + cipher.decryptor().finalize()
                if len(block) < 7: return
                sid, m_type, idx, plen = struct.unpack('<BBI B', block[:7])
                if self.ignore_self and sid == self.src_id: return
                if self.use_anti_replay:
                    if sid in self.last_indices and idx <= self.last_indices[sid]: return
                    self.last_indices[sid] = idx
                if not self.verify_crc_hardened(block[:7+plen], block[7+plen:7+plen+2]): return
                payload, seq = block[7:7+plen], idx & 0xFF
            else:
                if len(processed_block) < 4: return
                sid, m_type, seq, plen = struct.unpack('BBBB', processed_block[:4])
                if self.ignore_self and sid == self.src_id: return
                raw_payload = processed_block[4:4+plen+2]
                if not self.verify_crc(raw_payload, plen, sid, m_type, seq): return
                payload = raw_payload[:plen]
                if self.use_comsec and self.comsec_key and m_type == 0:
                    if len(payload) < 16: return
                    nonce, ct = payload[:16], payload[16:]
                    cipher = Cipher(algorithms.AES(self.comsec_key), modes.CTR(nonce), backend=default_backend())
                    payload = cipher.decryptor().update(ct) + cipher.decryptor().finalize()

            # 4. Dispatch
            payload = payload.split(b'\x00')[0]
            t_name = {0:"DATA", 1:"SYN", 2:"ACK", 3:"NACK", 5:"LEAP"}.get(m_type, "UNK")
            print(f"\033[92m[OK]\033[0m ID: {seq:03} | TYPE: {t_name} | RX: {payload}", flush=True)
            
            meta = pmt.make_dict()
            meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(m_type))
            meta = pmt.dict_add(meta, pmt.intern("seq"), pmt.from_long(seq))
            self.message_port_pub(pmt.intern("out"), pmt.cons(meta, pmt.init_u8vector(len(payload), list(payload))))
            
            diag = pmt.make_dict()
            diag = pmt.dict_add(diag, pmt.intern("confidence"), pmt.from_double(confidence * 100))
            diag = pmt.dict_add(diag, pmt.intern("fec_repairs"), pmt.from_long(repairs_made))
            diag = pmt.dict_add(diag, pmt.intern("crc_ok"), pmt.from_bool(True))
            self.message_port_pub(pmt.intern("diagnostics"), diag)

        except: pass

    def general_work(self, input_items, output_items):
        in0 = input_items[0]
        n = len(in0)
        is_tactical = ("LEVEL_6" in self.fec_mode or "LEVEL_7" in self.fec_mode or "LEVEL_8" in self.fec_mode)
        sync_val = self.sync_val_64 if is_tactical else self.sync_val_32
        threshold = 4 if is_tactical else 2

        for i in range(n):
            bit = int(in0[i]) & 1
            if self.state == "SEARCH":
                self.bit_buf = ((self.bit_buf << 1) | bit) & (0xFFFFFFFFFFFFFFFF if is_tactical else 0xFFFFFFFF)
                if (self.bit_buf ^ sync_val).bit_count() <= threshold:
                    self.is_inverted, self.state = False, "COLLECT"
                    self.recovered_bits, self.ccsk_buf = [], []; self.nrzi.reset(); self.scrambler.reset()
                    continue
                elif (self.bit_buf ^ ((0xFFFFFFFFFFFFFFFF if is_tactical else 0xFFFFFFFF) ^ sync_val)).bit_count() <= threshold:
                    self.is_inverted, self.state = True, "COLLECT"
                    self.recovered_bits, self.ccsk_buf = [], []; self.nrzi.reset(); self.scrambler.reset()
                    continue

            if self.state == "COLLECT":
                rx_bit = bit ^ (1 if self.is_inverted else 0)
                if self.use_ccsk:
                    self.ccsk_buf.append(rx_bit)
                    if len(self.ccsk_buf) >= 32:
                        sym, _ = self.ccsk.decode_chips(self.ccsk_buf)
                        for j in range(5): self.recovered_bits.append((sym >> (4-j)) & 1)
                        self.ccsk_buf = []
                else: self.recovered_bits.append(rx_bit)
                
                # Dynamic Bit Limit
                overhead = 9 if self.use_transec else 6
                raw_len = self.frame_size + overhead
                n_blks = (raw_len + 10) // 11
                fec_len = n_blks * 15 if self.use_fec else raw_len
                rows = 16
                pad_len = (rows - (fec_len % rows)) % rows
                phys_bytes = fec_len + pad_len
                
                if self.use_ccsk:
                    expected_bits = ((phys_bytes * 8 + 4) // 5) * 32
                else: expected_bits = phys_bytes * 8
                
                if len(self.recovered_bits) >= expected_bits:
                    bits_to_pack = self.recovered_bits[:expected_bits]
                    if len(bits_to_pack) % 8: bits_to_pack += [0]*(8-(len(bits_to_pack)%8))
                    bytes_data = np.packbits(np.array(bits_to_pack, dtype=np.uint8), bitorder='big')
                    self.process_recovered_block(bytes_data.tobytes(), 1.0)
                    self.state, self.bit_buf = "SEARCH", 0
        self.consume(0, n)
        return 0
