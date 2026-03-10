#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - GMSK Math Sandbox (Phase 8 Verification)

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

class GMSKSandbox(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self, "GMSK Sandbox")
        
        sps = 10
        config_path = "mission_configs/level3_resilient.yaml"
        
        self.pkt = packetizer(config_path=config_path, src_id=1)
        self.depkt = depacketizer(config_path=config_path, src_id=1, ignore_self=False)
        self.p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        # GMSK Modulation (BT=0.35 is tactical standard)
        self.mod = digital.gmsk_mod(samples_per_symbol=sps, bt=0.35, verbose=False, log=False)
        
        # GMSK Demodulation
        self.demod = digital.gmsk_demod(samples_per_symbol=sps, gain_mu=0.1, mu=0.5, omega_relative_limit=0.005, freq_error=0.0, verbose=False, log=False)

        self.src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len("GMSK_SUCCESS"), list("GMSK_TEST".encode()))), 500)
        self.msg_debug = blocks.message_debug()

        self.msg_connect((self.src, "strobe"), (self.pkt, "in"))
        self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
        
        # Stream Path: Mod -> Demod -> Depacketizer
        self.connect(self.p2s, self.mod, self.demod, self.depkt)
        self.msg_connect((self.depkt, "out"), (self.msg_debug, "store"))

    def check_results(self):
        time.sleep(3)
        n_msg = self.msg_debug.num_messages()
        if n_msg > 0:
            last_msg = self.msg_debug.get_message(n_msg-1)
            raw = bytes(pmt.u8vector_elements(pmt.cdr(last_msg))).decode('utf-8', errors='replace')
            print(f"\n\033[92m[SUCCESS]\033[0m GMSK Sandbox Recovered: {raw}")
            return True
        else:
            print("\n\033[91m[FAILURE]\033[0m GMSK Sandbox: No data recovered.")
            return False

if __name__ == "__main__":
    sb = GMSKSandbox()
    sb.start()
    success = sb.check_results()
    sb.stop(); sb.wait()
    sys.exit(0 if success else 1)
