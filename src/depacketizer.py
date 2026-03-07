#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Mission-Controlled Depacketizer (Burst-Viz Build v8.1)

import numpy as np
from gnuradio import gr
import pmt
import struct
import os
import sys
import yaml
import json
import time
from dsp_helper import MatrixInterleaver, Scrambler, NRZIEncoder, ManchesterEncoder, DSSSProcessor, CCSKProcessor

class depacketizer(gr.basic_block):
    def __init__(self, config_path="mission_configs/level1_soft_link.yaml", src_id=0, ignore_self=False):
        # Now has an output signature to pass bits + tags to the scope
        gr.basic_block.__init__(self, name="depacketizer", in_sig=[np.uint8], out_sig=[np.uint8])
        self.src_id = src_id
        self.ignore_self = ignore_self
        
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
        
        l_cfg = self.cfg['link_layer']
        self.rows = l_cfg.get('interleaver_rows', 8)
        self.use_fec = l_cfg.get('use_fec', True)
        self.use_interleaving = l_cfg.get('use_interleaving', True)
        self.use_whitening = l_cfg.get('use_whitening', True)
        self.use_nrzi = l_cfg.get('use_nrzi', True)
        self.use_manchester = l_cfg.get('use_manchester', False)
        self.use_comsec = False
        self.aes_gcm = None
        
        self.fec_mode = self.cfg.get('mission', {}).get('id', "")
        
        # Core Blocks
        self.interleaver = MatrixInterleaver(rows=self.rows)
        self.scrambler = Scrambler(mask=l_cfg.get('scrambler_mask', 0x48), seed=l_cfg.get('scrambler_seed', 0x7F))
        self.nrzi = NRZIEncoder()
        self.manchester = ManchesterEncoder()
        
        d_cfg = self.cfg.get('dsss', {})
        self.use_dsss = d_cfg.get('enabled', False)
        self.sf = d_cfg.get('spreading_factor', 31)
        self.dsss = DSSSProcessor(sf=self.sf, chipping_code=d_cfg.get('chipping_code', []))
        self.ccsk = CCSKProcessor()

        self.message_port_register_out(pmt.intern("out"))
        self.message_port_register_out(pmt.intern("diagnostics"))

        self.state = "SEARCH"
        self.syncword_bits = 0x3D4C5B6A
        self.bit_buf = 0
        self.recovered_bits = []
        self.chip_buf = []
        self.correlation_sum = 0
        self.bits_processed = 0
        self.is_inverted = False

        if not os.path.exists("mission_telemetry.jsonl"):
            with open("mission_telemetry.jsonl", "w") as f: pass
        self.telemetry_file = open("mission_telemetry.jsonl", "a", buffering=1)

    def verify_crc(self, data):
        if len(data) < 2: return False
        payload, received_crc = data[:-2], struct.unpack('>H', data[-2:])[0]
        crc = 0xFFFF
        for byte in payload:
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                else: crc <<= 1
            crc &= 0xFFFF
        return crc == received_crc

    def general_work(self, input_items, output_items):
        in0 = input_items[0]
        out = output_items[0]
        
        # Pass bits to output for scope
        out[:len(in0)] = in0

        for i in range(len(in0)):
            bit = int(in0[i]) & 1
            self.bit_buf = ((self.bit_buf << 1) | bit) & 0xFFFFFFFF

            # Hamming Distance Syncword Detection (Allow 2 bit errors)
            diff = self.bit_buf ^ self.syncword_bits
            dist = bin(diff).count('1')
            
            diff_inv = self.bit_buf ^ (0xFFFFFFFF ^ self.syncword_bits)
            dist_inv = bin(diff_inv).count('1')

            if dist <= 2 or dist_inv <= 2:
                self.is_inverted = (dist_inv <= 2)
                self.state = "COLLECT"
                self.recovered_bits = []
                self.chip_buf = []
                self.correlation_sum = 0
                self.bits_processed = 0
                self.nrzi.rx_state = 0
                self.scrambler.reset()
                
                # Add a tag for the GUI scope to trigger on
                tag_idx = self.nitems_written(0) + i
                self.add_item_tag(0, tag_idx, pmt.intern("rx_sync"), pmt.from_long(dist if dist <= 2 else dist_inv))
                continue

            if self.state == "COLLECT":
                if self.use_dsss:
                    self.chip_buf.append(1 if bit ^ (1 if self.is_inverted else 0) else -1)
                    if len(self.chip_buf) >= self.sf:
                        recovered_bit, correlation = self.dsss.despread(self.chip_buf)
                        self.recovered_bits.append(recovered_bit)
                        self.correlation_sum += abs(correlation)
                        self.bits_processed += 1
                        self.chip_buf = []
                else:
                    self.recovered_bits.append(bit ^ (1 if self.is_inverted else 0))
                
                target_bytes = 320 if "LINK-16" in self.fec_mode or "LEVEL_6" in self.fec_mode else 120
                target_bits = target_bytes * 8
                if self.use_manchester: target_bits *= 2

                if len(self.recovered_bits) >= target_bits:
                    bits = self.recovered_bits[:target_bits]
                    try:
                        if self.use_manchester: bits = self.manchester.decode(bits)
                        if self.use_nrzi: bits = self.nrzi.decode(bits)
                        
                        bytes_data = []; acc = 0; bc = 0
                        for bit in bits:
                            acc = (acc << 1) | bit; bc += 1
                            if bc == 8: bytes_data.append(acc); acc = 0; bc = 0
                        
                        data_block = bytes(bytes_data)
                        if self.use_whitening:
                            self.scrambler.reset()
                            data_block = self.scrambler.process(data_block)
                        if self.use_interleaving:
                            data_block = self.interleaver.deinterleave(data_block)
                        
                        sid, m_type, seq, plen = struct.unpack('BBBB', data_block[:4])
                        f_len = ((plen + 10) // 11) * 15 if self.use_fec and not ("LINK-16" in self.fec_mode) else plen
                        if "LINK-16" in self.fec_mode: f_len = ((plen + 14) // 15) * 31
                        
                        full_packet_len = 4 + f_len + 2
                        packet_for_crc = data_block[:full_packet_len]
                        crc_pass = self.verify_crc(packet_for_crc)
                        
                        conf = (self.correlation_sum / self.bits_processed / self.sf * 100.0) if self.bits_processed > 0 else 100.0
                        repairs = 0
                        payload = b''

                        if crc_pass:
                            if self.ignore_self and sid == self.src_id:
                                self.state = "SEARCH"; self.bit_buf = 0; continue

                            fec_payload = packet_for_crc[4:4+f_len]
                            if self.use_fec:
                                from rs_helper import RS1511, RS3115
                                if "LINK-16" in self.fec_mode or "LEVEL_6" in self.fec_mode:
                                    rs3115 = RS3115()
                                    p_bits = []
                                    for b in fec_payload: [p_bits.append((b >> (7-k)) & 1) for k in range(8)]
                                    decoded_bits = []
                                    for j in range(0, len(p_bits), 31*5):
                                        chunk = p_bits[j:j+31*5].ljust(31*5, 0)
                                        syms = [int(''.join(map(str, chunk[k*5:k*5+5])), 2) for k in range(31)]
                                        if not rs3115.is_valid(syms): repairs += 1
                                        dsyms = rs3115.decode(syms)
                                        for ds in dsyms:
                                            for k in range(5): decoded_bits.append((ds >> (4-k)) & 1)
                                    dec_bytes = []; acc = 0; bc = 0
                                    for b in decoded_bits:
                                        acc = (acc << 1) | b; bc += 1
                                        if bc == 8: dec_bytes.append(acc); acc = 0; bc = 0
                                    payload = bytes(dec_bytes)[:plen]
                                else:
                                    rs1511 = RS1511()
                                    decoded = b''
                                    for j in range(0, len(fec_payload), 15):
                                        nibs = []
                                        for b in fec_payload[j:j+15]: nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
                                        if not rs1511.is_valid(nibs): repairs += 1
                                        b1 = rs1511.decode(nibs[:15]); b2 = rs1511.decode(nibs[15:])
                                        all_n = b1 + b2
                                        for k in range(0, 22, 2): decoded += bytes([(all_n[k] << 4) | all_n[k+1]])
                                    payload = decoded[:plen]
                            else:
                                payload = fec_payload[:plen]
                            
                            if self.use_comsec and self.aes_gcm:
                                try:
                                    if len(payload) > 12:
                                        nonce, ciphertext = payload[:12], payload[12:]
                                        payload = self.aes_gcm.decrypt(nonce, ciphertext, None)
                                except Exception as e:
                                    print(f"\033[91m[COMSEC ERROR]\033[0m Decryption failed: {e}")
                                    self.state = "SEARCH"; self.bit_buf = 0; continue

                            type_map = {0: "DATA", 1: "SYN", 2: "ACK", 3: "NACK", 4: "AFH", 5: "AMC"}
                            t_name = type_map.get(m_type, "UNKNOWN")
                            color = "\033[92m" if m_type == 0 else "\033[96m"
                            print(f"{color}[OK]\033[0m ID: {seq:03} | TYPE: {t_name:4} | RX: {payload}")
                            
                            out_meta = pmt.make_dict()
                            out_meta = pmt.dict_add(out_meta, pmt.intern("type"), pmt.from_long(m_type))
                            out_meta = pmt.dict_add(out_meta, pmt.intern("seq"), pmt.from_long(seq))
                            out_meta = pmt.dict_add(out_meta, pmt.intern("src_id"), pmt.from_long(sid))
                            self.message_port_pub(pmt.intern("out"), pmt.cons(out_meta, pmt.init_u8vector(len(payload), list(payload))))
                        
                        diag_dict = pmt.make_dict()
                        diag_dict = pmt.dict_add(diag_dict, pmt.intern("crc_ok"), pmt.from_bool(crc_pass))
                        diag_dict = pmt.dict_add(diag_dict, pmt.intern("confidence"), pmt.from_double(conf))
                        diag_dict = pmt.dict_add(diag_dict, pmt.intern("fec_repairs"), pmt.from_long(repairs))
                        self.message_port_pub(pmt.intern("diagnostics"), diag_dict)
                        
                        telemetry = {"timestamp": time.time(), "event": "PACKET", "crc_ok": crc_pass, "confidence": round(conf, 2), "sequence": seq, "fec_repairs": repairs}
                        self.telemetry_file.write(json.dumps(telemetry) + "\n")
                        self.state = "SEARCH"; self.bit_buf = 0
                    except Exception as e:
                        print(f"Decode Error: {e}")
                        self.state = "SEARCH"; self.bit_buf = 0
        
        self.produce(0, len(in0))
        self.consume(0, len(in0))
        return 0

    def __del__(self):
        if hasattr(self, 'telemetry_file'): self.telemetry_file.close()
