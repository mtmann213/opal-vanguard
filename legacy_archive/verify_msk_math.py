#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - MSK Math Sandbox v2 (Phase 8 Verification)

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

class MSKSandbox(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self, "MSK Sandbox")
        
        sps = 10
        config_path = "mission_configs/level3_resilient.yaml"
        
        self.pkt = packetizer(config_path=config_path, src_id=1)
        self.depkt = depacketizer(config_path=config_path, src_id=1, ignore_self=False)
        self.p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        # MSK is CPFSK with h=0.5
        # Sensitivity = (pi * h) / sps = (pi * 0.5) / 10 = pi / 20
        msk_sensitivity = np.pi / sps
        self.mod = digital.cpfsk_mod(msk_sensitivity, 1.0, sps)
        
        # Quadrature Demod is the base for CPFSK/MSK recovery
        self.demod_quad = analog.quadrature_demod_cf(1.0 / msk_sensitivity)
        
        # Symbol Sync & Binary Slicing
        self.sync = digital.symbol_sync_fb(digital.TED_GARDNER, sps, 0.04, 1.0, 1.0, 1.5, 1, digital.constellation_bpsk().base(), digital.IR_MMSE_8TAPS, 128, [])
        self.binary_slice = digital.binary_slicer_fb()

        self.src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len("MSK_TEST"), list("MSK_TEST".encode()))), 500)
        self.msg_debug = blocks.message_debug()

        self.msg_connect((self.src, "strobe"), (self.pkt, "in"))
        self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
        
        # Stream Path: Mod -> Quadrature Demod -> Sync -> Slice -> Depacketizer
        self.connect(self.p2s, self.mod, self.demod_quad, self.sync, self.binary_slice, self.depkt)
        self.msg_connect((self.depkt, "out"), (self.msg_debug, "store"))

    def check_results(self):
        time.sleep(2)
        n_msg = self.msg_debug.num_messages()
        if n_msg > 0:
            last_msg = self.msg_debug.get_message(n_msg-1)
            raw = bytes(pmt.u8vector_elements(pmt.cdr(last_msg))).decode('utf-8', errors='replace')
            print(f"\n\033[92m[SUCCESS]\033[0m MSK Sandbox Recovered: {raw}")
            return True
        else:
            print("\n\033[91m[FAILURE]\033[0m MSK Sandbox: No data recovered.")
            return False

if __name__ == "__main__":
    from gnuradio import analog # Needed for quadrature_demod
    sb = MSKSandbox()
    sb.start()
    success = sb.check_results()
    sb.stop(); sb.wait()
    sys.exit(0 if success else 1)
