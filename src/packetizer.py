#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Performance-Grade Packetizer (v11.6)

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
    """
    Transforms raw application data into framed, encoded, and resilient PDUs.
    Handles CRC, RS-FEC, Interleaving, Whitening, and Syncword attachment.
    """
    def __init__(self, config_path="mission_configs/level1_soft_link.yaml", src_id=0):
        gr.basic_block.__init__(self, name="packetizer", in_sig=None, out_sig=None)
        self.src_id = src_id
        
        # Load Configuration
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
        self.comsec_key = bytes.fromhex(l_cfg.get('comsec_key', '00'*32)) if self.use_comsec else None
        
        # Initialize DSP Helpers once for efficiency
        self.interleaver = MatrixInterleaver(rows=l_cfg.get('interleaver_rows', 15))
        self.scrambler = Scrambler(mask=l_cfg.get('scrambler_mask', 0x48), seed=l_cfg.get('scrambler_seed', 0x7F))
        self.nrzi = NRZIEncoder()
        self.ccsk = CCSKProcessor()
        self.use_ccsk = (self.cfg.get('dsss', {}).get('enabled', False) and self.cfg.get('dsss', {}).get('type') == "CCSK")
        
        if self.use_fec:
            from rs_helper import RS1511
            self.rs = RS1511()

        # Ports
        self.message_port_register_in(pmt.intern("in"))
        self.message_port_register_out(pmt.intern("out"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)

    def calculate_crc16(self, data):
        """Standard CCITT CRC16 calculation."""
        crc = 0xFFFF
        for byte in data:
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                else: crc <<= 1
            crc &= 0xFFFF
        return crc

    def handle_msg(self, msg):
        """Processes a single message into a framed packet."""
        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        m_type, seq = 0, 0
        if pmt.is_dict(pmt.car(msg)):
            seq = pmt.to_long(pmt.dict_ref(pmt.car(msg), pmt.intern("seq"), pmt.from_long(0)))
            m_type = pmt.to_long(pmt.dict_ref(pmt.car(msg), pmt.intern("type"), pmt.from_long(0)))

        # 1. COMSEC Encryption (AES-CTR)
        if self.use_comsec and self.comsec_key and m_type == 0:
            nonce = os.urandom(16)
            cipher = Cipher(algorithms.AES(self.comsec_key), modes.CTR(nonce), backend=default_backend())
            payload = nonce + cipher.encryptor().update(payload) + cipher.encryptor().finalize()

        # 2. Header and CRC Injection
        true_plen = len(payload)
        header = struct.pack('BBBB', self.src_id, m_type, seq, true_plen)
        crc = self.calculate_crc16(header + payload)
        raw_block = header + payload + struct.pack('>H', crc)

        # 3. RS-FEC Encoding (Self-Healing)
        data_block = raw_block
        if self.use_fec:
            fec_payload = b''
            for i in range(0, len(raw_block), 11):
                chunk = raw_block[i:i+11].ljust(11, b'\x00')
                nibs = []
                for b in chunk: nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
                # Encode both nibble streams (11 -> 15 per nibble)
                all_e = self.rs.encode(nibs[:11]) + self.rs.encode(nibs[11:])
                # Pack 30 nibbles back into 15 bytes
                for k in range(0, 30, 2): fec_payload += bytes([( (all_e[k] << 4) | all_e[k+1] )])
            data_block = fec_payload

        # 4. Final Formatting (Padding, Interleaving, Whitening)
        packet = data_block.ljust(self.frame_size, b'\x00')[:self.frame_size]
        if self.use_interleaving: packet = self.interleaver.interleave(packet)
        if self.use_whitening: self.scrambler.reset(); packet = self.scrambler.process(packet)

        # 5. Modulation Domain Preparation
        is_ofdm = self.cfg['physical'].get('modulation', 'GFSK') == 'OFDM'
        if is_ofdm:
            # OFDM sends pure bytes
            self.message_port_pub(pmt.intern("out"), pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(packet), list(packet))))
        else:
            # Bit-stream modes (GFSK/BPSK) require explicit preamble/sync
            # 1. High-Efficiency Byte-to-Bit Conversion (Vectorized)
            bits = np.unpackbits(np.frombuffer(packet, dtype=np.uint8)).tolist()
            
            # Robust Tactical Detection (handles L6, L7, and LINK-16 variations)
            f_id = str(self.fec_mode).upper()
            is_tactical = ("LINK16" in f_id or "LINK-16" in f_id or "LEVEL_6" in f_id or "LEVEL_7" in f_id or "LEVEL_8" in f_id)
            
            if self.use_nrzi and not is_tactical: self.nrzi.tx_state = 0; bits = self.nrzi.encode(bits)
            
            final_bits = bits
            if self.use_ccsk:
                # 3. Vectorized CCSK Spreading (5-bit chunks)
                bits_arr = np.array(bits, dtype=np.uint8)
                # Ensure length is multiple of 5
                if len(bits_arr) % 5: bits_arr = np.append(bits_arr, np.zeros(5 - (len(bits_arr) % 5), dtype=np.uint8))
                
                # Reshape and convert to symbols (0-31)
                syms = np.packbits(bits_arr.reshape(-1, 5), axis=1, bitorder='big') >> 3
                final_bits = self.ccsk.vectorized_encode(syms.flatten())

            preamble = ([1,0]*(self.preamble_len // 2))[:self.preamble_len] # Flexible recovery pattern
            sync_val = 0x3D4C5B6AACE12345 if is_tactical else 0x3D4C5B6A
            sync_len = 64 if is_tactical else 32
            
            # 2. Vectorized Syncword Generation (Bit-shifting)
            syncword = [(sync_val >> i) & 1 for i in range(sync_len-1, -1, -1)]
            
            out_bits = preamble + syncword + final_bits
            self.message_port_pub(pmt.intern("out"), pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(out_bits), out_bits)))

    def work(self, i, o): return 0
