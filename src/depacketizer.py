#!/usr/bin/env python3
import numpy as np
from gnuradio import gr
import pmt
import struct
import os
import yaml
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from dsp_helper import MatrixInterleaver, Scrambler, NRZIEncoder

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
        self.interleaver = MatrixInterleaver(rows=l_cfg.get('interleaver_rows', 8))
        self.scrambler = Scrambler(mask=l_cfg.get('scrambler_mask', 0x48), seed=l_cfg.get('scrambler_seed', 0x7F))
        self.nrzi = NRZIEncoder()
        self.message_port_register_out(pmt.intern("out"))
        self.message_port_register_out(pmt.intern("diagnostics"))
        self.state, self.bit_buf, self.syncword_bits = "SEARCH", 0, 0x3D4C5B6A

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
        in0, out = input_items[0], output_items[0]
        n = min(len(in0), len(out)); out[:n] = in0[:n]
        for i in range(n):
            bit = int(in0[i]) & 1
            self.bit_buf = ((self.bit_buf << 1) | bit) & 0xFFFFFFFF
            if self.bit_buf == self.syncword_bits or self.bit_buf == (0xFFFFFFFF ^ self.syncword_bits):
                self.is_inverted = (self.bit_buf == (0xFFFFFFFF ^ self.syncword_bits))
                self.state, self.recovered_bits = "COLLECT", []
                self.nrzi.rx_state = 0; self.scrambler.reset()
                self.add_item_tag(0, self.nitems_written(0) + i - 64, pmt.intern("rx_sync"), pmt.from_long(0))
                continue
            if self.state == "COLLECT":
                self.recovered_bits.append(bit ^ (1 if self.is_inverted else 0))
                if len(self.recovered_bits) >= 960:
                    bits = self.recovered_bits[:960]
                    try:
                        if self.use_nrzi: bits = self.nrzi.decode(bits)
                        bytes_data = []
                        for j in range(0, 960, 8):
                            acc = 0
                            for k in range(8): acc = (acc << 1) | bits[j+k]
                            bytes_data.append(acc)
                        data_block = bytes(bytes_data)
                        if self.use_whitening: self.scrambler.reset(); data_block = self.scrambler.process(data_block)
                        if self.use_interleaving: data_block = self.interleaver.deinterleave(data_block)
                        sid, m_type, seq, plen = struct.unpack('BBBB', data_block[:4])
                        if plen + 6 <= 120:
                            packet_for_crc = data_block[:plen+6]
                            if self.verify_crc(packet_for_crc):
                                if self.ignore_self and sid == self.src_id: pass
                                else:
                                    payload = packet_for_crc[4:-2]
                                    if self.use_fec:
                                        from rs_helper import RS1511
                                        rs, decoded = RS1511(), b''
                                        for j in range(0, len(payload), 15):
                                            nibs = []
                                            for b in payload[j:j+15]: nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
                                            b1, b2 = rs.decode(nibs[:15]), rs.decode(nibs[15:])
                                            all_n = b1 + b2
                                            for k in range(0, 22, 2): decoded += bytes([(all_n[k] << 4) | all_n[k+1]])
                                        payload = decoded
                                    if self.use_comsec and self.comsec_key and m_type == 0:
                                        nonce, ct = payload[:16], payload[16:]
                                        cipher = Cipher(algorithms.AES(self.comsec_key), modes.CTR(nonce), backend=default_backend())
                                        decryptor = cipher.decryptor()
                                        # Decrypt and then SLICE to plen (minus COMSEC overhead)
                                        payload = (decryptor.update(ct) + decryptor.finalize())[:plen]
                                    else:
                                        # Slice non-encrypted payloads to plen
                                        payload = payload[:plen]

                                    t_name = {0:"DATA", 1:"SYN", 2:"ACK"}.get(m_type, "UNK")
                                    print(f"\033[92m[OK]\033[0m ID: {seq:03} | TYPE: {t_name} | RX: {payload}")
                                    meta = pmt.make_dict()
                                    meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(m_type))
                                    self.message_port_pub(pmt.intern("out"), pmt.cons(meta, pmt.init_u8vector(len(payload), list(payload))))
                            
                            # Link Health Diagnostics
                            diag_dict = pmt.make_dict()
                            diag_dict = pmt.dict_add(diag_dict, pmt.intern("crc_ok"), pmt.from_bool(crc_pass))
                            diag_dict = pmt.dict_add(diag_dict, pmt.intern("confidence"), pmt.from_double(100.0))
                            diag_dict = pmt.dict_add(diag_dict, pmt.intern("fec_repairs"), pmt.from_long(0))
                            self.message_port_pub(pmt.intern("diagnostics"), diag_dict)
                    except Exception as e: print(f"Decode Error: {e}")
                    self.state, self.bit_buf = "SEARCH", 0
        self.produce(0, n); self.consume(0, n); return 0
