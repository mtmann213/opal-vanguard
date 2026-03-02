#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Link 16 Mode Verification

import os
import sys
import yaml
import time
import pmt
from gnuradio import gr, blocks, pdu

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer

def test_link16_loopback():
    print("--- [TEST] Link 16 Digital Loopback ---")
    
    # We'll use the link16_config.yaml we created
    config_path = "mission_configs/level6_link16.yaml"
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found.")
        return False
        
    tb = gr.top_block()
    pkt = packetizer(config_path=config_path)
    depkt = depacketizer(config_path=config_path)
    p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
    unp = blocks.unpack_k_bits_bb(8) 
    msg_debug = blocks.message_debug()
    
    tb.msg_connect((pkt, "out"), (p2s, "pdus"))
    tb.connect(p2s, unp)
    tb.connect(unp, depkt)
    tb.msg_connect((depkt, "out"), (msg_debug, "store"))
    
    tb.start()
    test_payload = b"LINK-16 SECURE DATA TEST"
    print(f"Sending: {test_payload}")
    pkt.handle_msg(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(test_payload), list(test_payload))))
    
    success = False
    start_time = time.time()
    while time.time() - start_time < 3.0: 
        if msg_debug.num_messages() > 0:
            recv_payload = bytes(pmt.u8vector_elements(pmt.cdr(msg_debug.get_message(0))))
            print(f"Received: {recv_payload}")
            if test_payload in recv_payload:
                success = True; break
        time.sleep(0.1)
    
    tb.stop(); tb.wait()
    print(f"Result: {'SUCCESS' if success else 'FAILURE'}")
    return success

if __name__ == "__main__":
    if test_link16_loopback():
        sys.exit(0)
    else:
        sys.exit(1)
