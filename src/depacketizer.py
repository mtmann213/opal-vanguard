#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Dual-Domain Super-Vectorized Depacketizer (v16.1.0 Standard-Pivot)

import numpy as np
from gnuradio import gr
import pmt
import struct
import os
import yaml
import time
import threading
from collections import deque
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from dsp_helper import MatrixInterleaver, Scrambler, NRZIEncoder, CCSKProcessor
from numpy.lib.stride_tricks import sliding_window_view

class depacketizer(gr.basic_block):
    def __init__(self, config_path="mission_configs/level1_soft_link.yaml", src_id=0, ignore_self=False):
        # v16.1.0: Standard-Pivot Baseline. This engine is bit-only.
        # Sample-level processing (FFT/Sync) is offloaded to C++ blocks.
        gr.basic_block.__init__(self, name="depacketizer", in_sig=[np.uint8], out_sig=None)
        
        with open(config_path, 'r') as f: self.cfg = yaml.safe_load(f)
        self.src_id, self.ignore_self = src_id, ignore_self
        l_cfg = self.cfg.get('link_layer', {})
        self.frame_size, self.fec_mode = l_cfg.get('frame_size', 120), self.cfg.get('mission', {}).get('id', "")
        self.use_fec, self.use_interleaving = l_cfg.get('use_fec', True), l_cfg.get('use_interleaving', True)
        self.use_whitening, self.use_nrzi = l_cfg.get('use_whitening', True), l_cfg.get('use_nrzi', True)
        
        self.sync_hex = self.cfg.get('physical', {}).get('syncword', "0x3D4C5B6A")
        self.sync_val = int(self.sync_hex, 16); self.sync_len = (len(self.sync_hex) - 2) * 4
        self.threshold = max(1, self.sync_len // 16)
        self.target_bits = np.array([int(b) for b in format(self.sync_val, f'0{self.sync_len}b')], dtype=np.uint8)
        self.target_inv = 1 - self.target_bits
        
        self.use_comsec = l_cfg.get('use_comsec', False); self.comsec_key = bytes.fromhex(l_cfg.get('comsec_key', '00'*32)) if self.use_comsec else None
        self.interleaver = MatrixInterleaver(rows=l_cfg.get('interleaver_rows', 15))
        self.scrambler = Scrambler(mask=l_cfg.get('scrambler_mask', 0x48), seed=l_cfg.get('scrambler_seed', 0x7F))
        self.nrzi, self.ccsk = NRZIEncoder(), CCSKProcessor()
        if self.use_fec:
            from rs_helper import RS1511
            self.rs = RS1511()

        self.pdu_queue = deque(maxlen=50); self.worker_active = True
        self.worker_thread = threading.Thread(target=self._logic_worker, daemon=True); self.worker_thread.start()
        self.message_port_register_out(pmt.intern("out")); self.message_port_register_out(pmt.intern("diagnostics"))
        self.state, self.recovered_bits = "SEARCH", []

    def _logic_worker(self):
        while self.worker_active:
            if not self.pdu_queue: time.sleep(0.005); continue
            data_block, confidence = self.pdu_queue.popleft(); self.process_recovered_block(data_block, confidence)

    def verify_crc(self, payload, true_plen, sid, m_type, seq):
        if len(payload) < (true_plen + 2): return False
        extracted_crc = struct.unpack('>H', payload[true_plen:true_plen+2])[0]; crc = 0xFFFF; header_base = struct.pack('BBBB', sid, m_type, seq, true_plen)
        for byte in (header_base + payload[:true_plen]):
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                else: crc <<= 1
            crc &= 0xFFFF
        return crc == extracted_crc

    def process_recovered_block(self, data_block, confidence):
        try:
            if self.use_whitening: self.scrambler.reset(); data_block = self.scrambler.process(data_block)
            if self.use_interleaving: data_block = self.interleaver.deinterleave(data_block)
            processed_block = data_block; repairs_made = 0
            if self.use_fec:
                healed = bytearray()
                for j in range(0, len(data_block), 15):
                    chunk = data_block[j:j+15]
                    if len(chunk) < 15: break
                    nibs = []; [nibs.extend([(b >> 4) & 0x0F, b & 0x0F]) for b in chunk]
                    dn1, e1 = self.rs.decode(nibs[:15]); dn2, e2 = self.rs.decode(nibs[15:]); repairs_made += (e1 + e2); combined = dn1 + dn2
                    for k in range(0, 22, 2): healed.append((combined[k] << 4) | combined[k+1])
                processed_block = bytes(healed)
            sid, m_type, seq, true_plen = struct.unpack('BBBB', processed_block[:4])
            payload_zone = processed_block[4:4+true_plen+2]; crc_pass = self.verify_crc(payload_zone, true_plen, sid, m_type, seq)
            if crc_pass:
                if not (self.ignore_self and sid == self.src_id):
                    payload = payload_zone[:true_plen]
                    if self.use_comsec and self.comsec_key and m_type == 0:
                        nonce, ct = payload[:16], payload[16:]; cipher = Cipher(algorithms.AES(self.comsec_key), modes.CTR(nonce), backend=default_backend()); payload = cipher.decryptor().update(ct) + cipher.decryptor().finalize()
                    payload = payload.split(b'\x00')[0]; t_name = {0:"DATA", 1:"SYN", 2:"ACK", 3:"NACK"}.get(m_type, "UNK"); print(f"\033[92m[OK]\033[0m ID: {seq:03} | TYPE: {t_name} | RX: {payload}")
                    meta = pmt.make_dict(); meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(m_type)); self.message_port_pub(pmt.intern("out"), pmt.cons(meta, pmt.init_u8vector(len(payload), list(payload))))
                diag = pmt.make_dict(); diag = pmt.dict_add(diag, pmt.intern("crc_ok"), pmt.PMT_T); diag = pmt.dict_add(diag, pmt.intern("confidence"), pmt.from_double(confidence * 100.0)); diag = pmt.dict_add(diag, pmt.intern("fec_repairs"), pmt.from_long(repairs_made)); self.message_port_pub(pmt.intern("diagnostics"), diag)
        except: pass

    def general_work(self, input_items, output_items):
        in0 = input_items[0]; n = len(in0)
        if self.state == "SEARCH":
            if n < self.sync_len: return 0
            bits = in0 & 1
            try:
                windows = sliding_window_view(bits, self.sync_len)
                dists_n, dists_i = np.sum(windows != self.target_bits, axis=1), np.sum(windows != self.target_inv, axis=1)
                m_n, m_i = np.where(dists_n <= self.threshold)[0], np.where(dists_i <= self.threshold)[0]
                t = None
                if len(m_n) > 0: t = m_n[0]; self.is_inverted = False
                elif len(m_i) > 0: t = m_i[0]; self.is_inverted = True
                if t is not None:
                    self.state, self.recovered_bits = "COLLECT", []
                    self.consume(0, t + self.sync_len); self.nrzi.reset(); self.scrambler.reset(); return 0
            except: pass
            self.consume(0, max(0, n - self.sync_len + 1)); return 0
        if self.state == "COLLECT":
            is_tactical = ("LEVEL_6" in self.fec_mode or "LEVEL_7" in self.fec_mode)
            bits_per_frame = (self.frame_size * 8); chips_per_frame = (bits_per_frame // 5) * 32 if is_tactical else bits_per_frame
            needed = chips_per_frame - len(self.recovered_bits); to_take = min(n, needed); chunk = in0[:to_take] & 1
            if self.is_inverted: chunk = chunk ^ 1
            self.recovered_bits.extend(chunk.tolist())
            if len(self.recovered_bits) >= chips_per_frame:
                raw_chips = np.array(self.recovered_bits[:chips_per_frame], dtype=np.uint8)
                if is_tactical:
                    symbols = np.abs(np.dot(np.where(raw_chips.reshape(-1, 32) == 1, 1, -1), self.ccsk.lut_matrix.T)).argmax(axis=1)
                    mask = 2**np.arange(5)[::-1]; bits_arr = ((symbols[:, None] & mask) > 0).astype(np.uint8).flatten()
                else: bits_arr = raw_chips
                if self.use_nrzi and not is_tactical: bits_arr = np.array(self.nrzi.decode(bits_arr.tolist()), dtype=np.uint8)
                self.pdu_queue.append((np.packbits(bits_arr).tobytes(), 1.0)); self.state, self.recovered_bits = "SEARCH", []
            self.consume(0, to_take); return 0
