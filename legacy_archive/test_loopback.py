#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Full Digital Loopback Test (FIXED)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, pdu
import pmt
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer

def test_loopback(config_path="mission_configs/level1_soft_link.yaml"):
    print(f"Testing {config_path}...")
    
    class LoopbackTest(gr.top_block):
        def __init__(self, cfg):
            gr.top_block.__init__(self)
            self.pkt = packetizer(config_path=cfg)
            self.p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
            self.depkt = depacketizer(config_path=cfg)
            self.msg_debug = blocks.message_debug()
            self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
            self.connect(self.p2s, self.depkt)
            self.msg_connect((self.depkt, "out"), (self.msg_debug, "print"))
            
        def send_pdu(self, payload_bytes):
            meta = pmt.make_dict()
            blob = pmt.init_u8vector(len(payload_bytes), list(payload_bytes))
            pdu = pmt.cons(meta, blob)
            self.pkt.handle_msg(pdu)

    tb = LoopbackTest(config_path)
    tb.start()
    tb.send_pdu(b"Project Opal Vanguard: Mission Successful")
    time.sleep(0.5)
    tb.stop()
    tb.wait()
    print("-" * 40)

if __name__ == "__main__":
    for level in [1, 2, 3, 4]:
        cfg = f"mission_configs/level{level}_" + (
            "soft_link.yaml" if level == 1 else 
            "repairable.yaml" if level == 2 else 
            "resilient.yaml" if level == 3 else
            "stealth.yaml")
        test_loopback(cfg)
