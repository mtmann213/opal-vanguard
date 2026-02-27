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

def test_loopback():
    print("Testing Full Digital Loopback (TX -> Bits -> RX)...")
    
    class LoopbackTest(gr.top_block):
        def __init__(self):
            gr.top_block.__init__(self)
            
            # TX (PDU -> Bits)
            self.pkt = packetizer()
            self.p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
            self.unp = blocks.unpack_k_bits_bb(8)
            
            # RX (Bits -> PDU)
            self.depkt = depacketizer()
            self.msg_debug = blocks.message_debug()
            
            # Connections
            # TX
            self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
            self.connect(self.p2s, self.unp)
            
            # Channel (Bit-to-Bit)
            self.connect(self.unp, self.depkt)
            
            # RX
            self.msg_connect((self.depkt, "out"), (self.msg_debug, "print"))
            
        def send_pdu(self, payload_bytes):
            meta = pmt.make_dict()
            blob = pmt.init_u8vector(len(payload_bytes), list(payload_bytes))
            pdu = pmt.cons(meta, blob)
            self.pkt.handle_msg(pdu)

    tb = LoopbackTest()
    tb.start()
    
    test_payload = b"Project Opal Vanguard: Mission Successful"
    print(f"Sending: {test_payload}")
    tb.send_pdu(test_payload)
    
    time.sleep(0.5)
    tb.stop()
    tb.wait()
    print("Loopback test complete.")

if __name__ == "__main__":
    test_loopback()
