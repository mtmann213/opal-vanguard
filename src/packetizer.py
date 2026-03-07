#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Mission-Controlled Packetizer (Stability Build v8.0)

import numpy as np
from gnuradio import gr
import pmt
import struct
import os
import sys
import yaml
from dsp_helper import MatrixInterleaver, Scrambler, NRZIEncoder, ManchesterEncoder, DSSSProcessor, CCSKProcessor

class packetizer(gr.basic_block):
    def __init__(self, config_path="mission_configs/level1_soft_link.yaml", src_id=0):
        gr.basic_block.__init__(self, name="packetizer", in_sig=None, out_sig=None)
        self.src_id = src_id
        
        # Load Mission Config
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
        
        # Init DSP components
        self.interleaver = MatrixInterleaver(rows=self.rows)
        self.scrambler = Scrambler(mask=l_cfg.get('scrambler_mask', 0x48), seed=l_cfg.get('scrambler_seed', 0x7F))
        self.nrzi = NRZIEncoder()
        self.manchester = ManchesterEncoder()
        
        # Spreading
        d_cfg = self.cfg.get('dsss', {})
        self.use_dsss = d_cfg.get('enabled', False)
        self.dsss_type = d_cfg.get('type', "DSSS")
        self.dsss = DSSSProcessor(sf=d_cfg.get('spreading_factor', 31), chipping_code=d_cfg.get('chipping_code', []))
        self.ccsk = CCSKProcessor()

        # In/Out Ports
        self.message_port_register_in(pmt.intern("in"))
        self.message_port_register_out(pmt.intern("out"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)

    def handle_msg(self, msg):
        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        
        # Default metadata
        m_type, seq = 0, 0
        if pmt.is_dict(pmt.car(msg)):
            seq = pmt.to_long(pmt.dict_ref(pmt.car(msg), pmt.intern("seq"), pmt.from_long(0)))
            m_type = pmt.to_long(pmt.dict_ref(pmt.car(msg), pmt.intern("type"), pmt.from_long(0)))

        # 1. COMSEC Encryption (Must happen before Header packing)
        if self.use_comsec and self.aes_gcm:
            nonce = os.urandom(12)
            ciphertext = self.aes_gcm.encrypt(nonce, payload, None)
            payload = nonce + ciphertext

        # 2. Forward Error Correction (FEC)
        if self.use_fec:
            from rs_helper import RS1511, RS3115
            if "LINK-16" in self.fec_mode or "LEVEL_6" in self.fec_mode:
                rs3115 = RS3115()
                fec_payload = b''
                p_bits = []
                for b in payload: [p_bits.append((b >> (7-i)) & 1) for i in range(8)]
                for i in range(0, len(p_bits), 15*5):
                    chunk = p_bits[i:i+15*5].ljust(15*5, 0)
                    syms = [int(''.join(map(str, chunk[k*5:k*5+5])), 2) for k in range(15)]
                    encoded_syms = rs3115.encode(syms)
                    for s in encoded_syms:
                        for k in range(5): fec_payload += bytes([(s >> (4-k)) & 1])
                # Convert bits back to bytes for header packing
                f_bytes = []
                for j in range(0, len(fec_payload), 8):
                    b = 0
                    for k in range(8): b = (b << 1) | fec_payload[j+k]
                    f_bytes.append(b)
                payload = bytes(f_bytes)
            else:
                rs1511 = RS1511()
                fec_payload = b''
                for i in range(0, len(payload), 11):
                    chunk = payload[i:i+11].ljust(11, b'\x00')
                    nibs = []
                    for b in chunk: nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
                    e1 = rs1511.encode(nibs[:11]); e2 = rs1511.encode(nibs[11:])
                    all_e = e1 + e2
                    for k in range(0, 30, 2): fec_payload += bytes([(all_e[k] << 4) | all_e[k+1]])
                payload = fec_payload

        # 3. Assemble Header & Packet
        header = struct.pack('BBBB', self.src_id, m_type, seq, len(payload))
        packet = header + payload
        
        # CRC16
        crc = 0xFFFF
        for byte in packet:
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                else: crc <<= 1
            crc &= 0xFFFF
        packet += struct.pack('>H', crc)

        # 4. Padding & Interleaving
        target_bytes = 320 if "LINK-16" in self.fec_mode or "LEVEL_6" in self.fec_mode else 120
        packet = packet.ljust(target_bytes, b'\x00')[:target_bytes]
        
        if self.use_interleaving:
            packet = self.interleaver.interleave(packet)
        
        if self.use_whitening:
            self.scrambler.reset()
            packet = self.scrambler.process(packet)

        # 5. Bit-Level Processing
        bits = []
        for b in packet: [bits.append((b >> (7-i)) & 1) for i in range(8)]
        
        if self.use_nrzi:
            self.nrzi.tx_state = 0
            bits = self.nrzi.encode(bits)
            
        if self.use_manchester:
            bits = self.manchester.encode(bits)

        # 6. Spreading
        final_bits = []
        if self.use_dsss:
            if self.dsss_type == "CCSK":
                for i in range(0, len(bits), 5):
                    sym = 0
                    for j in range(5): sym = (sym << 1) | bits[i+j]
                    final_bits.extend(self.ccsk.encode_symbol(sym))
            else:
                chips = self.dsss.spread(bits)
                final_bits = [1 if c > 0 else 0 for c in chips]
        else:
            final_bits = bits

        # 7. Framing (Preamble + Syncword + Data)
        preamble = [1,0]*256 # Robust 2ms preamble for USRP T/R switch settling
        syncword = [int(b) for b in format(0x3D4C5B6A, '032b')]
        out_bits = preamble + syncword + final_bits
        
        # Output as UNPACKED bits (one bit per byte)
        self.message_port_pub(pmt.intern("out"), pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(out_bits), out_bits)))

    def work(self, i, o): return 0
