#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Mission-Controlled Depacketizer (with Scoring & Logging)

import numpy as np
from gnuradio import gr
import pmt
import struct
import os
import sys
import yaml
import binascii
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from rs_helper import RS1511, RS3115
from dsp_helper import MatrixInterleaver, DSSSProcessor, NRZIEncoder, ManchesterEncoder, Scrambler

class depacketizer(gr.basic_block):
    def __init__(self, config_path="mission_configs/level1_soft_link.yaml"):
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
        
        self.fec_mode = self.cfg.get('mission', {}).get('id', "")
        self.rs1511 = RS1511()
        self.rs3115 = RS3115()
        
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
        self.correlation_sum = 0
        self.bits_processed = 0
        self.is_inverted = False
        
        self.log_file = open("mission_history.log", "a")
        self.log_file.write(f"\n--- MISSION START: {time.ctime()} ---\n")
        self.log_file.flush()

    def verify_crc(self, data):
        if self.crc_type == "NONE": return True
        if self.crc_type == "CRC16":
            if len(data) < 2: return False
            payload, received_crc = data[:-2], struct.unpack('>H', data[-2:])[0]
            crc = 0xFFFF
            for byte in payload:
                crc ^= byte << 8
                for _ in range(8):
                    if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                    else: crc = (crc << 1)
                    crc &= 0xFFFF
            return crc == received_crc
        elif self.crc_type == "CRC32":
            if len(data) < 4: return False
            payload, received_crc = data[:-4], struct.unpack('>I', data[-4:])[0]
            calc_crc = binascii.crc32(payload) & 0xFFFFFFFF
            return calc_crc == received_crc
        return False

    def general_work(self, input_items, output_items):
        in0 = input_items[0]
        for i in range(len(in0)):
            bit = int(in0[i]) & 1
            self.bit_buf = ((self.bit_buf << 1) | bit) & 0xFFFFFFFF
            
            # Check for Syncword (allows reset even if in COLLECT state)
            if self.bit_buf == self.syncword_bits or self.bit_buf == (0xFFFFFFFF ^ self.syncword_bits):
                self.is_inverted = (self.bit_buf == (0xFFFFFFFF ^ self.syncword_bits))
                self.state = "COLLECT"
                self.recovered_bits = []
                self.nrzi.reset()
                self.chip_buf = []
                self.active_pkt_len = 0
                self.correlation_sum = 0
                self.bits_processed = 0
                continue 
                    
            if self.state == "COLLECT":
                if self.use_dsss:
                    chip = 1 if bit == 1 else -1
                    if self.is_inverted: chip *= -1
                    self.chip_buf.append(chip)
                    if len(self.chip_buf) == self.sf:
                        chunk = np.array(self.chip_buf); corr = np.sum(chunk * self.dsss.code)
                        self.correlation_sum += abs(corr); self.bits_processed += 1
                        self.recovered_bits.append(1 if corr > 0 else 0)
                        self.chip_buf = []
                else:
                    self.recovered_bits.append(bit ^ (1 if self.is_inverted else 0))

                # If not interleaving, we can peek at the header to find the exact length
                if not self.use_interleaving and self.active_pkt_len == 0:
                    header_bits_needed = 24 * (2 if self.use_manchester else 1)
                    if len(self.recovered_bits) >= header_bits_needed:
                        h_bits = self.recovered_bits[:header_bits_needed]
                        if self.use_manchester: h_bits = self.manchester.decode(h_bits)
                        # Temporary NRZI decode for header
                        tnrzi = NRZIEncoder(); tnrzi.rx_state = 0
                        if self.use_nrzi: h_bits = tnrzi.decode(h_bits)
                        
                        h_bytes = []
                        acc = 0; bc = 0
                        for b in h_bits:
                            acc = (acc << 1) | b; bc += 1
                            if bc == 8: h_bytes.append(acc); acc = 0; bc = 0
                        h_data = bytes(h_bytes)
                        if self.use_whitening: h_data = self.scrambler.process(h_data)
                        
                        try:
                            m_type, seq, plen = struct.unpack('BBB', h_data[:3])
                            if self.use_fec:
                                if "LINK-16" in self.fec_mode: f_len = (((((plen + 14) // 15) * 15) * 8 + 74) // 75) * 31 * 5 // 8
                                else: f_len = ((plen + 10) // 11) * 15
                            else: f_len = plen
                            c_len = 4 if self.crc_type == "CRC32" else (2 if self.crc_type == "CRC16" else 0)
                            self.active_pkt_len = 3 + f_len + c_len
                        except: pass

                # Determine target bits for processing
                if self.use_interleaving:
                    target_bytes = 256 if "LINK-16" in self.fec_mode or "LEVEL_6" in self.fec_mode else 120
                else:
                    target_bytes = self.active_pkt_len if self.active_pkt_len > 0 else 2048 # Fallback
                
                target_bits = target_bytes * 8
                if self.use_manchester: target_bits *= 2
                
                if len(self.recovered_bits) >= target_bits:
                    bits = self.recovered_bits[:target_bits]
                    if self.use_manchester: self.manchester.reset(); bits = self.manchester.decode(bits)
                    if self.use_nrzi: bits = self.nrzi.decode(bits)
                    
                    bytes_data = []
                    acc = 0; bc = 0
                    for bit in bits:
                        acc = (acc << 1) | bit; bc += 1
                        if bc == 8: bytes_data.append(acc); acc = 0; bc = 0
                    data_block = bytes(bytes_data)
                    
                    if self.use_whitening: data_block = self.scrambler.process(data_block)
                    if self.use_interleaving: data_block = self.interleaver.deinterleave(data_block, len(data_block))
                    
                    try:
                        m_type, seq, plen = struct.unpack('BBB', data_block[:3])
                        if self.use_fec:
                            if "LINK-16" in self.fec_mode:
                                padded_plen = ((plen + 14) // 15) * 15
                                num_blocks = (padded_plen * 8 + 74) // 75
                                f_len = (num_blocks * 31 * 5 + 7) // 8
                            else: f_len = ((plen + 10) // 11) * 15
                        else: f_len = plen
                        
                        c_len = 4 if self.crc_type == "CRC32" else (2 if self.crc_type == "CRC16" else 0)
                        full_packet_len = 3 + f_len + c_len
                        packet_for_crc = data_block[:full_packet_len]
                        
                        conf = (self.correlation_sum / self.bits_processed / self.sf * 100.0) if self.bits_processed > 0 else 100.0
                        
                        if self.verify_crc(packet_for_crc):
                            fec_payload = packet_for_crc[3:3+f_len]
                            if self.use_fec:
                                if "LINK-16" in self.fec_mode:
                                    p_bits = []
                                    for b in fec_payload:
                                        for k in range(8): p_bits.append((b >> (7-k)) & 1)
                                    decoded_payload_bits = []
                                    for j in range(0, (len(p_bits)//(31*5))*(31*5), 31*5):
                                        chunk = p_bits[j:j+31*5]
                                        symbols = []
                                        for k in range(31):
                                            s = 0
                                            for m in range(5): s = (s << 1) | chunk[k*5+m]
                                            symbols.append(s)
                                        dsyms = self.rs3115.decode(symbols)
                                        for ds in dsyms:
                                            for k in range(5): decoded_payload_bits.append((ds >> (4-k)) & 1)
                                    dec_bytes = []
                                    acc = 0; bc = 0
                                    for bit in decoded_payload_bits:
                                        acc = (acc << 1) | bit; bc += 1
                                        if bc == 8: dec_bytes.append(acc); acc = 0; bc = 0
                                    payload = bytes(dec_bytes)[:plen]
                                else:
                                    decoded = b''
                                    for j in range(0, len(fec_payload), 15):
                                        nibs = []
                                        for b in fec_payload[j:j+15]: nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
                                        b1 = self.rs1511.decode(nibs[:15]); b2 = self.rs1511.decode(nibs[15:])
                                        all = b1 + b2
                                        for k in range(0, 22, 2): decoded += bytes([(all[k] << 4) | all[k+1]])
                                    payload = decoded[:plen]
                            else: payload = fec_payload[:plen]
                            
                            print(f"\033[92m[OK]\033[0m ID: {seq:03} | Conf: {conf:5.1f}% | RX: {payload}")
                            
                            diag_dict = pmt.make_dict()
                            diag_dict = pmt.dict_add(diag_dict, pmt.intern("crc_ok"), pmt.from_bool(True))
                            diag_dict = pmt.dict_add(diag_dict, pmt.intern("inverted"), pmt.from_bool(self.is_inverted))
                            self.message_port_pub(pmt.intern("diagnostics"), diag_dict)
                            
                            self.log_file.write(f"{time.ctime()} SUCCESS: Seq={seq} Conf={conf:.1f} % Payload={payload}\n")
                            self.message_port_pub(pmt.intern("out"), pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(payload), list(payload))))
                        else:
                            print(f"\033[91m[FAIL]\033[0m CRC Error | Conf: {conf:5.1f}%")
                            diag_dict = pmt.make_dict()
                            diag_dict = pmt.dict_add(diag_dict, pmt.intern("crc_ok"), pmt.from_bool(False))
                            self.message_port_pub(pmt.intern("diagnostics"), diag_dict)
                            self.log_file.write(f"{time.ctime()} FAILURE: CRC Error Conf={conf:.1f}%\n")
                        self.log_file.flush()
                    except Exception as e:
                        print(f"Decode Error: {e}")
                    
                    self.state = "SEARCH"; self.bit_buf = 0
        self.consume(0, len(in0)); return 0
    def __del__(self):
        if hasattr(self, 'log_file'): self.log_file.close()
