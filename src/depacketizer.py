#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Threaded Link-Layer Offload Depacketizer (v15.9.2)

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
        gr.basic_block.__init__(self, name="depacketizer", in_sig=[np.uint8], out_sig=None)
        self.src_id, self.ignore_self = src_id, ignore_self
        
        with open(config_path, 'r') as f: self.cfg = yaml.safe_load(f)
        l_cfg = self.cfg.get('link_layer', {})
        p_cfg = self.cfg.get('physical', {})
        self.frame_size = l_cfg.get('frame_size', 120)
        self.use_fec = l_cfg.get('use_fec', True)
        self.use_interleaving = l_cfg.get('use_interleaving', True)
        self.use_whitening = l_cfg.get('use_whitening', True)
        self.use_nrzi = l_cfg.get('use_nrzi', True)
        self.fec_mode = self.cfg.get('mission', {}).get('id', "")
        
        # Dynamic Waveform Parameters
        self.sync_hex = p_cfg.get('syncword', "0x3D4C5B6A")
        self.sync_val = int(self.sync_hex, 16)
        self.sync_len = (len(self.sync_hex) - 2) * 4
        self.threshold = max(1, self.sync_len // 16)
        self.target_bits = np.array([int(b) for b in format(self.sync_val, f'0{self.sync_len}b')], dtype=np.uint8)
        self.target_inv = 1 - self.target_bits
        
        self.use_comsec = l_cfg.get('use_comsec', False)
        self.comsec_key = bytes.fromhex(l_cfg.get('comsec_key', '00'*32)) if self.use_comsec else None
        self.interleaver = MatrixInterleaver(rows=l_cfg.get('interleaver_rows', 15))
        self.scrambler = Scrambler(mask=l_cfg.get('scrambler_mask', 0x48), seed=l_cfg.get('scrambler_seed', 0x7F))
        self.nrzi = NRZIEncoder(); self.ccsk = CCSKProcessor()
        if self.use_fec:
            from rs_helper import RS1511
            self.rs = RS1511()

        # v15.9.2: Async Math Worker
        # We offload the heavy RS-FEC and Interleaving to a background thread
        self.pdu_queue = deque(maxlen=50)
        self.worker_active = True
        self.worker_thread = threading.Thread(target=self._logic_worker, daemon=True)
        self.worker_thread.start()

        self.message_port_register_out(pmt.intern("out"))
        self.message_port_register_out(pmt.intern("diagnostics"))
        self.message_port_register_in(pmt.intern("pdu_in"))
        self.set_msg_handler(pmt.intern("pdu_in"), self.handle_pdu)
        
        self.state = "SEARCH"; self.recovered_bits = []; self.is_inverted = False

    def _logic_worker(self):
        """Background thread that drains the PDU queue and performs heavy math."""
        while self.worker_active:
            if not self.pdu_queue:
                time.sleep(0.005); continue
            data_block, confidence = self.pdu_queue.popleft()
            self.process_recovered_block(data_block, confidence)

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

    def handle_pdu(self, msg):
        data_block = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        self.pdu_queue.append((data_block, 1.0))

    def process_recovered_block(self, data_block, confidence):
        try:
            if self.use_whitening: self.scrambler.reset(); data_block = self.scrambler.process(data_block)
            if self.use_interleaving: data_block = self.interleaver.deinterleave(data_block)
            
            processed_block = data_block
            repairs_made = 0
            if self.use_fec:
                healed = bytearray()
                for j in range(0, len(data_block), 15):
                    chunk = data_block[j:j+15]
                    if len(chunk) < 15: break
                    nibs = []
                    for b in chunk: nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
                    dn1, e1 = self.rs.decode(nibs[:15]); dn2, e2 = self.rs.decode(nibs[15:])
                    repairs_made += (e1 + e2)
                    combined = dn1 + dn2
                    for k in range(0, 22, 2): healed.append((combined[k] << 4) | combined[k+1])
                processed_block = bytes(healed)

            sid, m_type, seq, true_plen = struct.unpack('BBBB', processed_block[:4])
            payload_zone = processed_block[4:4+true_plen+2]
            crc_pass = self.verify_crc(payload_zone, true_plen, sid, m_type, seq)
            
            if crc_pass:
                if not (self.ignore_self and sid == self.src_id):
                    payload = payload_zone[:true_plen]
                    if self.use_comsec and self.comsec_key and m_type == 0:
                        nonce, ct = payload[:16], payload[16:]
                        cipher = Cipher(algorithms.AES(self.comsec_key), modes.CTR(nonce), backend=default_backend())
                        payload = cipher.decryptor().update(ct) + cipher.decryptor().finalize()
                    
                    payload = payload.split(b'\x00')[0]
                    t_name = {0:"DATA", 1:"SYN", 2:"ACK", 3:"NACK"}.get(m_type, "UNK")
                    print(f"\033[92m[OK]\033[0m ID: {seq:03} | TYPE: {t_name} | RX: {payload}")
                    meta = pmt.make_dict(); meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(m_type))
                    self.message_port_pub(pmt.intern("out"), pmt.cons(meta, pmt.init_u8vector(len(payload), list(payload))))
            
                diag = pmt.make_dict()
                diag = pmt.dict_add(diag, pmt.intern("crc_ok"), pmt.PMT_T)
                diag = pmt.dict_add(diag, pmt.intern("confidence"), pmt.from_double(confidence * 100.0))
                diag = pmt.dict_add(diag, pmt.intern("fec_repairs"), pmt.from_long(repairs_made))
                self.message_port_pub(pmt.intern("diagnostics"), diag)
        except: pass

    def general_work(self, input_items, output_items):
        in0 = input_items[0]; n = len(in0)
        
        if self.state == "SEARCH":
            if n < self.sync_len: return 0
            bits = in0 & 1
            try:
                windows = sliding_window_view(bits, self.sync_len)
                dists = np.sum(windows != self.target_bits, axis=1)
                matches = np.where(dists <= self.threshold)[0]
                if len(matches) > 0:
                    idx = matches[0]; self.is_inverted, self.state = False, "COLLECT"
                    self.consume(0, idx + self.sync_len); self.recovered_bits = []
                    self.nrzi.reset(); self.scrambler.reset(); return 0
                
                dists_inv = np.sum(windows != self.target_inv, axis=1)
                matches_inv = np.where(dists_inv <= self.threshold)[0]
                if len(matches_inv) > 0:
                    idx = matches_inv[0]; self.is_inverted, self.state = True, "COLLECT"
                    self.consume(0, idx + self.sync_len); self.recovered_bits = []
                    self.nrzi.reset(); self.scrambler.reset(); return 0
            except: pass
            self.consume(0, max(0, n - self.sync_len + 1)); return 0

        if self.state == "COLLECT":
            is_tactical = ("LEVEL_6" in self.fec_mode or "LEVEL_7" in self.fec_mode)
            bits_per_frame = (self.frame_size * 8)
            chips_per_frame = (bits_per_frame // 5) * 32 if is_tactical else bits_per_frame
            needed = chips_per_frame - len(self.recovered_bits)
            to_take = min(n, needed)
            chunk = in0[:to_take] & 1
            if self.is_inverted: chunk = chunk ^ 1
            self.recovered_bits.extend(chunk.tolist())
            
            if len(self.recovered_bits) >= chips_per_frame:
                raw_chips = np.array(self.recovered_bits[:chips_per_frame], dtype=np.uint8)
                if is_tactical:
                    chips_bipolar = np.where(raw_chips == 1, 1, -1)
                    symbols_chips = chips_bipolar.reshape(-1, 32)
                    correlations = np.abs(np.dot(symbols_chips, self.ccsk.lut_matrix.T))
                    best_symbols = np.argmax(correlations, axis=1)
                    mask = 2**np.arange(5)[::-1]
                    bits_arr = ((best_symbols[:, None] & mask) > 0).astype(np.uint8).flatten()
                else:
                    bits_arr = raw_chips
                
                if self.use_nrzi and not is_tactical:
                    bits_arr = np.array(self.nrzi.decode(bits_arr.tolist()), dtype=np.uint8)
                
                # v15.9.2: Offload to worker thread
                self.pdu_queue.append((np.packbits(bits_arr).tobytes(), 1.0))
                self.state, self.recovered_bits = "SEARCH", []
            
            self.consume(0, to_take); return 0
