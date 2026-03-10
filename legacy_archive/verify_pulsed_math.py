#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Pulsed Waveform Sandbox (Phase 10 Verification)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, digital, pdu
import pmt
import time

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer

class PulsedSandbox(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self, "Pulsed Sandbox")
        
        # 1. Config
        sps = 10
        samp_rate = 2000000
        config_path = "mission_configs/level6_link16.yaml"
        
        self.pkt = packetizer(config_path=config_path, src_id=1)
        self.depkt = depacketizer(config_path=config_path, src_id=1, ignore_self=False)
        self.p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        # 2. MSK Modulation
        bit_rate = samp_rate / sps
        sens = (2.0 * np.pi * (bit_rate/4.0)) / samp_rate
        self.mod = digital.gfsk_mod(sps, sens, 1.0, False, False, False)
        
        # 3. THE PULSE GATE (The Phase 10 Heart)
        # We alternate between 1.0 (On) and 0.0 (Off)
        # For 2.0 Msps, 13 samples is ~6.5 microseconds.
        # We will gate every 10 samples (1 symbol at SPS=10)
        pulse_pattern = [1.0]*10 + [0.0]*10 # 50% Duty Cycle for extreme testing
        self.gate = blocks.vector_source_c(pulse_pattern, True)
        self.muly = blocks.multiply_cc()
        
        # 4. Demodulation
        self.demod = digital.gfsk_demod(sps, sens, 0.1, 0.5, 0.005, 0.0)
        
        # 5. Data
        test_msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len("PULSE_OK"), list("PULSE_OK".encode())))
        self.src = blocks.message_strobe(test_msg, 500)
        self.msg_debug = blocks.message_debug()

        # Connections
        self.msg_connect((self.src, "strobe"), (self.pkt, "in"))
        self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
        
        # Stream Path: Mod -> Gated -> Demod -> Depkt
        self.connect(self.p2s, self.mod)
        self.connect(self.mod, (self.muly, 0))
        self.connect(self.gate, (self.muly, 1))
        self.connect(self.muly, self.demod, self.depkt)
        
        self.msg_connect((self.depkt, "out"), (self.msg_debug, "store"))

    def check_results(self):
        time.sleep(3)
        n_msg = self.msg_debug.num_messages()
        if n_msg > 0:
            last_msg = self.msg_debug.get_message(n_msg-1)
            raw = bytes(pmt.u8vector_elements(pmt.cdr(last_msg))).decode('utf-8', errors='replace')
            print(f"\n\033[92m[SUCCESS]\033[0m Pulsed Sandbox Recovered: {raw}")
            return True
        else:
            print("\n\033[91m[FAILURE]\033[0m Pulsed Sandbox: Syncword lost in the gaps.")
            return False

if __name__ == "__main__":
    print("--- STARTING PHASE 10 PULSE VERIFICATION ---")
    sb = PulsedSandbox()
    sb.start()
    success = sb.check_results()
    sb.stop(); sb.wait()
    sys.exit(0 if success else 1)
