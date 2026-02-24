#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Full Digital Loopback Test

import os
import sys
import numpy as np
from gnuradio import gr, blocks
import pmt
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer
from whitener import whitener

def test_loopback():
    print("Testing Full Digital Loopback (TX -> Scramble -> RX)...")
    
    class LoopbackTest(gr.top_block):
        def __init__(self):
            gr.top_block.__init__(self)
            
            # TX
            self.pkt = packetizer()
            self.whit_tx = whitener(seed=0x7F)
            self.pdu_to_stream = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
            self.unpacker = blocks.unpack_k_bits_bb(8)
            
            # RX
            self.whit_rx = whitener(seed=0x7F)
            self.packer = blocks.pack_k_bits_bb(8)
            self.depkt = depacketizer()
            self.msg_debug = blocks.message_debug()
            
            # Connections
            # TX: PDU -> Stream -> Bits -> Whiten
            self.msg_connect((self.pkt, "out"), (self.pdu_to_stream, "pdus"))
            self.connect(self.pdu_to_stream, self.unpacker, self.whit_tx)
            
            # Loopback: Whiten (TX) -> Whiten (RX) (self-undoing)
            self.connect(self.whit_tx, self.whit_rx)
            
            # RX: Whiten (RX) -> Pack -> Depacketizer -> PDU Out
            self.connect(self.whit_rx, self.packer, self.depkt)
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
    
    time.sleep(0.2)
    tb.stop()
    tb.wait()
    print("Loopback test complete.")

if __name__ == "__main__":
    test_loopback()
