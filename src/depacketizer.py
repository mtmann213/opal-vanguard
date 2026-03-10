#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - High-Performance Depacketizer (v11.7)

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
    """
    High-performance Link Layer recovery engine.
    Handles bit-synchronization, NRZI decoding, FEC healing, and COMSEC decryption.
    """
    def __init__(self, config_path="mission_configs/level1_soft_link.yaml", src_id=0, ignore_self=False):
        gr.basic_block.__init__(self, name="depacketizer", in_sig=[np.uint8], out_sig=None)
        self.src_id, self.ignore_self = src_id, ignore_self
        
        # Load Configuration
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
        self.comsec_key = bytes.fromhex(l_cfg.get('comsec_key', '00'*32)) if self.use_comsec else None
        
        # Persistent DSP Helpers
        self.interleaver = MatrixInterleaver(rows=l_cfg.get('interleaver_rows', 15))
        self.scrambler = Scrambler(mask=l_cfg.get('scrambler_mask', 0x48), seed=l_cfg.get('scrambler_seed', 0x7F))
        self.nrzi = NRZIEncoder()
        self.ccsk = CCSKProcessor()
        self.use_ccsk = (self.cfg.get('dsss', {}).get('enabled', False) and self.cfg.get('dsss', {}).get('type') == "CCSK")
        
        if self.use_fec:
            from rs_helper import RS1511
            self.rs = RS1511()

        # Ports
        self.message_port_register_out(pmt.intern("out"))
        self.message_port_register_out(pmt.intern("diagnostics"))
        self.message_port_register_in(pmt.intern("pdu_in")) # For Native PDU modes
        self.set_msg_handler(pmt.intern("pdu_in"), self.handle_pdu)
        
        # State Machine Initialization
        self.state = "SEARCH"
        self.bit_buf = 0
        self.recovered_bits = []
        self.ccsk_buf = []
        self.is_inverted = False
        
        # Optimization: Pre-calculate syncwords
        self.sync_val_32 = 0x3D4C5B6A
        self.sync_val_64 = 0x3D4C5B6AACE12345

    def verify_crc(self, payload, true_plen, sid, m_type, seq):
        """Validates the CRC16 integrity of the recovered payload."""
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
        """Direct entry point for pre-synchronized PDU payloads (e.g. OFDM)."""
        data_block = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        self.process_recovered_block(data_block, 1.0)

    def process_recovered_block(self, data_block, confidence):
        """Executes the full recovery pipeline on a raw byte block."""
        try:
            # 1. Un-Formatting
            if self.use_whitening: self.scrambler.reset(); data_block = self.scrambler.process(data_block)
            if self.use_interleaving: data_block = self.interleaver.deinterleave(data_block)
            
            # 2. RS-FEC Healing
            processed_block = data_block
            repairs_made = 0
            if self.use_fec:
                healed = b''
                for j in range(0, len(data_block), 15):
                    chunk = data_block[j:j+15]
                    if len(chunk) < 15: break
                    nibs = []
                    for b in chunk: nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
                    # Decode and track errors
                    d_nibs_1, errs1 = self.rs.decode(nibs[:15])
                    d_nibs_2, errs2 = self.rs.decode(nibs[15:])
                    repairs_made += (errs1 + errs2)
                    for k in range(0, 11): healed += bytes([( (d_nibs_1[k] << 4) | d_nibs_2[k] )]) if k < 11 else b''
                # Redo healing logic for symmetry with packetizer v11.6
                healed = b''
                for j in range(0, len(data_block), 15):
                    chunk = data_block[j:j+15]
                    if len(chunk) < 15: break
                    nibs = []
                    for b in chunk: nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
                    # Decode pairs
                    dn1, e1 = self.rs.decode(nibs[:15])
                    dn2, e2 = self.rs.decode(nibs[15:])
                    repairs_made += (e1 + e2)
                    combined = dn1 + dn2
                    for k in range(0, 22, 2): healed += bytes([( (combined[k] << 4) | combined[k+1] )])
                processed_block = healed

            # 3. Header Extraction
            sid, m_type, seq, true_plen = struct.unpack('BBBB', processed_block[:4])
            payload_zone = processed_block[4:4+true_plen+2]
            
            # 4. Integrity Check
            crc_pass = self.verify_crc(payload_zone, true_plen, sid, m_type, seq)
            
            if crc_pass:
                if not (self.ignore_self and sid == self.src_id):
                    payload = payload_zone[:true_plen]
                    # COMSEC Decryption
                    if self.use_comsec and self.comsec_key and m_type == 0:
                        nonce, ct = payload[:16], payload[16:]
                        cipher = Cipher(algorithms.AES(self.comsec_key), modes.CTR(nonce), backend=default_backend())
                        payload = cipher.decryptor().update(ct) + cipher.decryptor().finalize()
                    
                    payload = payload.split(b'\x00')[0] # Remove padding
                    t_name = {0:"DATA", 1:"SYN", 2:"ACK", 3:"NACK"}.get(m_type, "UNK")
                    print(f"\033[92m[OK]\033[0m ID: {seq:03} | TYPE: {t_name} | RX: {payload}")
                    
                    # Publish to UI/Session
                    meta = pmt.make_dict(); meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(m_type))
                    self.message_port_pub(pmt.intern("out"), pmt.cons(meta, pmt.init_u8vector(len(payload), list(payload))))
            
            # 5. Telemetry
            diag = pmt.make_dict()
            diag = pmt.dict_add(diag, pmt.intern("crc_ok"), pmt.from_bool(crc_pass))
            diag = pmt.dict_add(diag, pmt.intern("confidence"), pmt.from_double(confidence * 100.0))
            diag = pmt.dict_add(diag, pmt.intern("fec_repairs"), pmt.from_long(repairs_made))
            self.message_port_pub(pmt.intern("diagnostics"), diag)
            
        except Exception as e:
            print(f"RECOVERY ERROR: {e}")

    def general_work(self, input_items, output_items):
        in0 = input_items[0]
        n = len(in0)
        
        is_ofdm = self.cfg['physical'].get('modulation', 'GFSK') == 'OFDM'
        is_tactical = ("LINK-16" in self.fec_mode or "LEVEL_6" in self.fec_mode or "LEVEL_7" in self.fec_mode)
        sync_val = self.sync_val_64 if is_tactical else self.sync_val_32
        threshold = 4 if is_tactical else 2

        for i in range(n):
            bit = int(in0[i]) & 1
            
            if self.state == "SEARCH":
                self.bit_buf = ((self.bit_buf << 1) | bit) & (0xFFFFFFFFFFFFFFFF if is_tactical else 0xFFFFFFFF)
                
                # High-Efficiency Bitwise Hamming Search
                found = False
                if (self.bit_buf ^ sync_val).bit_count() <= threshold:
                    self.is_inverted, found = False, True
                elif (self.bit_buf ^ ((0xFFFFFFFFFFFFFFFF if is_tactical else 0xFFFFFFFF) ^ sync_val)).bit_count() <= threshold:
                    self.is_inverted, found = True, True
                
                if found:
                    self.state = "COLLECT"
                    self.recovered_bits = []
                    self.ccsk_buf = []
                    self.nrzi.reset()
                    self.scrambler.reset()
                    continue

            if self.state == "COLLECT":
                rx_bit = bit ^ (1 if self.is_inverted else 0)
                
                if self.use_ccsk:
                    self.ccsk_buf.append(rx_bit)
                    if len(self.ccsk_buf) >= 32:
                        sym, _ = self.ccsk.decode_chips(self.ccsk_buf)
                        # Vectorized 5-bit expansion
                        for j in range(5): self.recovered_bits.append((sym >> (4-j)) & 1)
                        self.ccsk_buf = []
                else:
                    self.recovered_bits.append(rx_bit)
                
                if len(self.recovered_bits) >= (self.frame_size * 8):
                    # Optimized Bit-to-Byte packing using NumPy
                    bits_arr = np.array(self.recovered_bits[:self.frame_size * 8], dtype=np.uint8)
                    if self.use_nrzi and not is_tactical:
                        bits_arr = self.nrzi.decode(bits_arr.tolist()) # Maintain list for NRZI for now
                        bits_arr = np.array(bits_arr, dtype=np.uint8)
                    
                    bytes_data = np.packbits(bits_arr)
                    self.process_recovered_block(bytes_data.tobytes(), 1.0)
                    self.state = "SEARCH"
                    self.bit_buf = 0
                    self.recovered_bits = []

        self.consume(0, n)
        return 0
