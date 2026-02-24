#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Packetizer Test Script

import os
import sys
import numpy as np
from gnuradio import gr
from gnuradio import blocks
import pmt
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer

def test_packetizer():
    print("Testing Packetizer (PDU in -> PDU out)...")
    
    class PacketizerTest(gr.top_block):
        def __init__(self):
            gr.top_block.__init__(self)
            
            # PDU Source
            self.pdu_src = blocks.message_strobe(pmt.PMT_NIL, 1000)
            
            # Message mapping to convert strobe to custom PDU
            self.pdu_creator = blocks.message_debug() # Just a dummy to hold ports
            
            # Packetizer
            self.pkt = packetizer()
            
            # PDU Sink
            self.msg_debug = blocks.message_debug()
            
            self.msg_connect((self.pkt, "out"), (self.msg_debug, "print"))
            
        def send_pdu(self, payload_bytes):
            meta = pmt.make_dict()
            blob = pmt.init_u8vector(len(payload_bytes), list(payload_bytes))
            pdu = pmt.cons(meta, blob)
            self.pkt.handle_msg(pdu)

    tb = PacketizerTest()
    tb.start()
    
    test_payload = b"Opal"
    print(f"Sending Payload: {test_payload}")
    tb.send_pdu(test_payload)
    
    time.sleep(0.1)
    tb.stop()
    tb.wait()
    print("Packetizer test complete.")

if __name__ == "__main__":
    test_packetizer()
