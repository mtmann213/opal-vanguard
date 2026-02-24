#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Handshake Verification Test

import os
import sys
import numpy as np
from gnuradio import gr, blocks
import pmt
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer
from session_manager import session_manager

def test_handshake():
    print("Testing Session Handshake (SYN -> ACK -> DATA)...")
    
    class HandshakeTest(gr.top_block):
        def __init__(self):
            gr.top_block.__init__(self)
            
            # NODE A
            self.session_a = session_manager()
            self.pkt_a = packetizer()
            
            # NODE B
            self.session_b = session_manager()
            self.pkt_b = packetizer()
            
            # Shared Channel Logic
            self.depkt_a = depacketizer()
            self.depkt_b = depacketizer()
            
            self.p2s_a = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
            self.p2s_b = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
            
            # Unpacker converts bytes to bitstream for the depacketizer
            self.unp_a = blocks.unpack_k_bits_bb(8)
            self.unp_b = blocks.unpack_k_bits_bb(8)
            
            # A -> B path
            self.msg_connect((self.session_a, "pkt_out"), (self.pkt_a, "in"))
            self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
            self.connect(self.p2s_a, self.unp_a, self.depkt_b)
            self.msg_connect((self.depkt_b, "out"), (self.session_b, "msg_in"))
            
            # B -> A path
            self.msg_connect((self.session_b, "pkt_out"), (self.pkt_b, "in"))
            self.msg_connect((self.pkt_b, "out"), (self.p2s_b, "pdus"))
            self.connect(self.p2s_b, self.unp_b, self.depkt_a)
            self.msg_connect((self.depkt_a, "out"), (self.session_a, "msg_in"))

            # Monitoring
            self.debug = blocks.message_debug()
            self.msg_connect((self.session_a, "data_out"), (self.debug, "print"))

        def send_data(self, text):
            msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(text), list(text.encode())))
            self.session_a.handle_tx_request(msg)

    tb = HandshakeTest()
    tb.start()
    
    print("\n--- Triggering Data from Node A ---")
    tb.send_data("Hello Node B")
    
    time.sleep(0.5)
    print("\n--- Triggering Data again ---")
    tb.send_data("Opal Vanguard Status: Green")
    
    time.sleep(0.5)
    tb.stop()
    tb.wait()
    print("\nHandshake test complete.")

if __name__ == "__main__":
    test_handshake()
