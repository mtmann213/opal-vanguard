#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Mission-Controlled Packetizer (Deep FEC Build v10.4)

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
        l_cfg = self.cfg['link_layer']
        self.use_fec = l_cfg.get('use_fec', True)
        self.use_interleaving = l_cfg.get('use_interleaving', True)
        self.use_whitening = l_cfg.get('use_whitening', True)
        self.use_nrzi = l_cfg.get('use_nrzi', True)
        self.use_comsec = False
        self.comsec_key = None
        self.fec_mode = self.cfg.get('mission', {}).get('id', "")
        
        d_cfg = self.cfg.get('dsss', {})
        self.use_ccsk = (d_cfg.get('enabled', False) and d_cfg.get('type') == "CCSK")
        self.ccsk = CCSKProcessor()
        self.interleaver = MatrixInterleaver(rows=l_cfg.get('interleaver_rows', 15))
        self.scrambler = Scrambler(mask=l_cfg.get('scrambler_mask', 0x48), seed=l_cfg.get('scrambler_seed', 0x7F))
        self.nrzi = NRZIEncoder()
        
        self.message_port_register_in(pmt.intern("in"))
        self.message_port_register_out(pmt.intern("out"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)

    def handle_msg(self, msg):
        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        m_type, seq = 0, 0
        if pmt.is_dict(pmt.car(msg)):
            seq = pmt.to_long(pmt.dict_ref(pmt.car(msg), pmt.intern("seq"), pmt.from_long(0)))
            m_type = pmt.to_long(pmt.dict_ref(pmt.car(msg), pmt.intern("type"), pmt.from_long(0)))

        # 1. COMSEC (Only DATA)
        if self.use_comsec and self.comsec_key and m_type == 0:
            nonce = os.urandom(16)
            cipher = Cipher(algorithms.AES(self.comsec_key), modes.CTR(nonce), backend=default_backend())
            payload = nonce + cipher.encryptor().update(payload) + cipher.encryptor().finalize()

        # 2. INNER CRC (Protect payload only)
        crc = 0xFFFF
        true_plen = len(payload)
        for byte in payload:
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                else: crc <<= 1
            crc &= 0xFFFF
        
        # 3. Assemble Unified Raw Block (Header + Payload + CRC)
        raw_block = struct.pack('BBBB', self.src_id, m_type, seq, true_plen) + payload + struct.pack('>H', crc)

        # 4. Deep FEC Encoding (RS 31,15 over GF(32))
        data_to_transmit = raw_block
        if self.use_fec:
            from rs_helper import RS3115
            rs = RS3115()
            fec_payload = b''
            # Link 16 standard: 15 symbols (75 bits) -> 31 symbols (155 bits)
            # We'll pack 15 bytes into one RS(31,15) block by treating each byte as a symbol
            for i in range(0, len(raw_block), 15):
                chunk = list(raw_block[i:i+15].ljust(15, b'\x00'))
                encoded = rs.encode(chunk)
                # Pack 31 symbols (5 bits each) into bytes
                bits = []
                for sym in encoded:
                    for k in range(5): bits.append((sym >> (4-k)) & 1)
                # Convert 155 bits to 20 bytes
                bits += [0] * 5 # Pad to 160 bits
                for j in range(0, 160, 8):
                    acc = 0
                    for k in range(8): acc = (acc << 1) | bits[j+k]
                    fec_payload += bytes([acc])
            data_to_transmit = fec_payload

        # 5. Final Assembly & Interleaving
        is_tactical = ("LINK-16" in self.fec_mode or "LEVEL_6" in self.fec_mode)
        target_bytes = 160 if is_tactical else 120
        packet = data_to_transmit.ljust(target_bytes, b'\x00')[:target_bytes]
        
        if self.use_interleaving: packet = self.interleaver.interleave(packet)
        if self.use_whitening: self.scrambler.reset(); packet = self.scrambler.process(packet)

        # 6. Conversion
        bits = []
        for b in packet: [bits.append((b >> (7-i)) & 1) for i in range(8)]
        if self.use_nrzi and not is_tactical: self.nrzi.tx_state = 0; bits = self.nrzi.encode(bits)

        # 7. CCSK
        final_bits = []
        if self.use_ccsk:
            for i in range(0, len(bits), 5):
                chunk = bits[i:i+5]; sym = 0
                for b in chunk: sym = (sym << 1) | b
                final_bits.extend(self.ccsk.encode_symbol(sym))
        else: final_bits = bits

        # 8. Framing
        preamble = [1,0]*1024
        syncword = [int(b) for b in format(0x3D4C5B6AACE12345 if is_tactical else 0x3D4C5B6A, '064b' if is_tactical else '032b')]
        out_bits = preamble + syncword + final_bits
        self.message_port_pub(pmt.intern("out"), pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(out_bits), out_bits)))

    def work(self, i, o): return 0
