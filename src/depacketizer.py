#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Mission-Controlled Depacketizer (Single-Header Build v10.1)

import numpy as np
from gnuradio import gr
import pmt
import struct
import os
import yaml
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from dsp_helper import MatrixInterleaver, Scrambler, NRZIEncoder, CCSKProcessor

class depacketizer(gr.basic_block):
    def __init__(self, config_path="mission_configs/level1_soft_link.yaml", src_id=0, ignore_self=False):
        gr.basic_block.__init__(self, name="depacketizer", in_sig=[np.uint8], out_sig=[np.uint8])
        self.src_id, self.ignore_self = src_id, ignore_self
        with open(config_path, 'r') as f: self.cfg = yaml.safe_load(f)
        l_cfg = self.cfg['link_layer']
        self.use_fec = l_cfg.get('use_fec', True)
        self.use_interleaving = l_cfg.get('use_interleaving', True)
        self.use_whitening = l_cfg.get('use_whitening', True)
        self.use_nrzi = l_cfg.get('use_nrzi', True)
        self.use_comsec = False
        self.comsec_key = None
        self.interleaver = MatrixInterleaver(rows=l_cfg.get('interleaver_rows', 15))
        self.scrambler = Scrambler(mask=l_cfg.get('scrambler_mask', 0x48), seed=l_cfg.get('scrambler_seed', 0x7F))
        self.nrzi = NRZIEncoder()
        self.fec_mode = self.cfg.get('mission', {}).get('id', "")
        d_cfg = self.cfg.get('dsss', {})
        self.use_ccsk = (d_cfg.get('enabled', False) and d_cfg.get('type') == "CCSK")
        self.ccsk = CCSKProcessor()
        self.message_port_register_out(pmt.intern("out"))
        self.message_port_register_out(pmt.intern("diagnostics"))
        self.state, self.bit_buf = "SEARCH", 0
        self.syncword_32 = 0x3D4C5B6A
        self.syncword_64 = 0x3D4C5B6AACE12345

    def verify_crc(self, payload, true_plen):
        """Verify inner CRC based strictly on payload bits."""
        if len(payload) < (true_plen + 2): return False
        extracted_data = payload[:true_plen]
        extracted_crc = struct.unpack('>H', payload[true_plen:true_plen+2])[0]
        crc = 0xFFFF
        for byte in extracted_data:
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                else: crc <<= 1
            crc &= 0xFFFF
        return crc == extracted_crc

    def general_work(self, input_items, output_items):
        in0, out = input_items[0], output_items[0]
        n = min(len(in0), len(out)); out[:n] = in0[:n]
        is_tactical = ("LINK-16" in self.fec_mode or "LEVEL_6" in self.fec_mode)
        for i in range(n):
            bit = int(in0[i]) & 1
            self.bit_buf = ((self.bit_buf << 1) | bit) & 0xFFFFFFFFFFFFFFFF
            found_sync = False
            if is_tactical:
                if bin(self.bit_buf ^ self.syncword_64).count('1') <= 4: self.is_inverted = False; found_sync = True
                elif bin(self.bit_buf ^ (0xFFFFFFFFFFFFFFFF ^ self.syncword_64)).count('1') <= 4: self.is_inverted = True; found_sync = True
            else:
                buf32 = self.bit_buf & 0xFFFFFFFF
                if bin(buf32 ^ self.syncword_32).count('1') <= 2: self.is_inverted = False; found_sync = True
                elif bin(buf32 ^ (0xFFFFFFFF ^ self.syncword_32)).count('1') <= 2: self.is_inverted = True; found_sync = True
            
            if found_sync:
                self.state, self.recovered_bits, self.ccsk_buf = "COLLECT", [], []
                self.nrzi.rx_state = 0; self.scrambler.reset(); self.ccsk_conf_sum, self.ccsk_sym_count = 0, 0
                self.add_item_tag(0, self.nitems_written(0) + i - 64, pmt.intern("rx_sync"), pmt.from_long(0))
                continue
            
            if self.state == "COLLECT":
                rx_bit = bit ^ (1 if self.is_inverted else 0)
                if self.use_ccsk:
                    self.ccsk_buf.append(rx_bit)
                    if len(self.ccsk_buf) >= 32:
                        sym, conf = self.ccsk.decode_chips(self.ccsk_buf)
                        self.ccsk_conf_sum += conf; self.ccsk_sym_count += 1
                        for j in range(5): self.recovered_bits.append((sym >> (4-j)) & 1)
                        self.ccsk_buf = []
                else: self.recovered_bits.append(rx_bit)
                
                target_bytes = 120
                target_bits = target_bytes * 8
                if len(self.recovered_bits) >= target_bits:
                    avg_conf = self.ccsk_conf_sum / self.ccsk_sym_count if self.ccsk_sym_count > 0 else 1.0
                    if avg_conf < 0.6: self.state, self.bit_buf = "SEARCH", 0; continue
                    
                    bits = self.recovered_bits[:target_bits]
                    try:
                        if self.use_nrzi and not is_tactical: bits = self.nrzi.decode(bits)
                        bytes_data = []
                        for j in range(0, target_bits, 8):
                            acc = 0
                            for k in range(8): acc = (acc << 1) | bits[j+k]
                            bytes_data.append(acc)
                        data_block = bytes(bytes_data)
                        
                        # 1. De-whiten FIRST
                        if self.use_whitening: self.scrambler.reset(); data_block = self.scrambler.process(data_block)
                        # 2. De-interleave SECOND
                        if self.use_interleaving: data_block = self.interleaver.deinterleave(data_block)
                        
                        # 3. HEALING STAGE (FEC Decode EVERYTHING first)
                        decoded_block = data_block
                        if self.use_fec:
                            from rs_helper import RS1511
                            rs, healed = RS1511(), b''
                            for j in range(0, len(data_block), 15):
                                chunk = data_block[j:j+15]
                                if len(chunk) < 15: break
                                nibs = []
                                for b in chunk: nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
                                d_nibs = rs.decode(nibs[:15]) + rs.decode(nibs[15:])
                                for k in range(0, 22, 2): healed += bytes([( (d_nibs[k] << 4) | d_nibs[k+1] )])
                            decoded_block = healed
                        
                        # 4. Extract Header from HEALED data
                        sid, m_type, seq, true_plen = struct.unpack('BBBB', decoded_block[:4])
                        if true_plen > 0 and true_plen < 100:
                            print(f"[DEBUG] Recovered: sid={sid} type={m_type} seq={seq} plen={true_plen}")

                        # 5. CRC Check on HEALED payload
                        # Payload starts at index 4 in the HEALED block
                        payload_zone = decoded_block[4:4+true_plen+2]
                        crc_pass = self.verify_crc(payload_zone, true_plen)
                        
                        if crc_pass:
                            if not (self.ignore_self and sid == self.src_id):
                                payload = payload_zone[:true_plen]
                                if self.use_comsec and self.comsec_key and m_type == 0:
                                    nonce, ct = payload[:16], payload[16:]
                                    cipher = Cipher(algorithms.AES(self.comsec_key), modes.CTR(nonce), backend=default_backend())
                                    payload = cipher.decryptor().update(ct) + cipher.decryptor().finalize()
                                payload = payload.split(b'\x00')[0]
                                t_name = {0:"DATA", 1:"SYN", 2:"ACK"}.get(m_type, "UNK")
                                print(f"\033[92m[OK]\033[0m ID: {seq:03} | TYPE: {t_name} | RX: {payload} | CONF: {avg_conf:.2f}")
                                meta = pmt.make_dict()
                                meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(m_type))
                                self.message_port_pub(pmt.intern("out"), pmt.cons(meta, pmt.init_u8vector(len(payload), list(payload))))
                        elif true_plen > 0 and true_plen < 100:
                            print(f"\033[91m[CRC FAIL]\033[0m ID: {seq:03} | LEN: {true_plen} | CONF: {avg_conf:.2f}")
                        
                        diag_dict = pmt.make_dict()
                        diag_dict = pmt.dict_add(diag_dict, pmt.intern("crc_ok"), pmt.from_bool(crc_pass))
                        diag_dict = pmt.dict_add(diag_dict, pmt.intern("confidence"), pmt.from_double(avg_conf * 100.0))
                        self.message_port_pub(pmt.intern("diagnostics"), diag_dict)
                    except Exception as e: print(f"Decode Error: {e}")
                    self.state, self.bit_buf = "SEARCH", 0
        self.produce(0, n); self.consume(0, n); return 0
