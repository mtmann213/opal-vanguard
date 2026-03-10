#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - GMSK (via GFSK-Framework) Sandbox

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

class GMSKProvenSandbox(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self, "GMSK Proven Sandbox")
        
        sps = 10
        samp_rate = 2000000
        config_path = "mission_configs/level3_resilient.yaml"
        
        self.pkt = packetizer(config_path=config_path, src_id=1)
        self.depkt = depacketizer(config_path=config_path, src_id=1, ignore_self=False)
        self.p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        # GMSK Parameters
        # Sensitivity for h=0.5: (pi * 0.5) / sps = pi / 20
        # Sensitivity for GFSK block is: (2 * pi * freq_dev) / samp_rate
        # For GMSK, freq_dev = bit_rate / 4 = (samp_rate/sps) / 4
        # freq_dev = 2000000 / 40 = 50000
        freq_dev = (samp_rate / sps) / 4.0
        gmsk_sens = (2.0 * np.pi * freq_dev) / samp_rate
        
        print(f"GMSK Emulation: Sens={gmsk_sens:.4f} | BT=0.35")
        
        self.mod = digital.gfsk_mod(sps, gmsk_sens, 0.35, False, False, False)
        self.demod = digital.gfsk_demod(sps, gmsk_sens, 0.1, 0.5, 0.005, 0.0)

        self.src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len("GMSK_SUCCESS"), list("GMSK_TEST".encode()))), 500)
        self.msg_debug = blocks.message_debug()

        self.msg_connect((self.src, "strobe"), (self.pkt, "in"))
        self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
        
        self.connect(self.p2s, self.mod, self.demod, self.depkt)
        self.msg_connect((self.depkt, "out"), (self.msg_debug, "store"))

    def check_results(self):
        time.sleep(3)
        n_msg = self.msg_debug.num_messages()
        if n_msg > 0:
            last_msg = self.msg_debug.get_message(n_msg-1)
            raw = bytes(pmt.u8vector_elements(pmt.cdr(last_msg))).decode('utf-8', errors='replace')
            print(f"\n\033[92m[SUCCESS]\033[0m GMSK (Proven) Sandbox Recovered: {raw}")
            return True
        else:
            print("\n\033[91m[FAILURE]\033[0m GMSK (Proven) Sandbox: No data recovered.")
            return False

if __name__ == "__main__":
    sb = GMSKProvenSandbox()
    sb.start()
    success = sb.check_results()
    sb.stop(); sb.wait()
    sys.exit(0 if success else 1)
