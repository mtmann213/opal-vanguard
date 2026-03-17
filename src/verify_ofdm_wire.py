#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - OFDM Digital Wire-Audit (v1.0)

import os
import sys
import yaml
import time
import pmt
import numpy as np
from gnuradio import gr, blocks, pdu

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from packetizer import packetizer
from depacketizer import depacketizer

def run_wire_audit():
    print("\n" + "="*50)
    print("   OPAL VANGUARD: OFDM DIGITAL WIRE-AUDIT   ")
    print("="*50)
    
    config_path = "mission_configs/level7_ofdm_master.yaml"
    with open(config_path, 'r') as f:
        cfg = yaml.safe_load(f)
    
    # We must ensure the test uses the same frame size as the mission
    print(f"[*] Auditing with Frame Size: {cfg['link_layer']['frame_size']} bytes")
    
    tb = gr.top_block()
    
    # Transmitter
    pkt = packetizer(config_path=config_path)
    # The packetizer in OFDM mode emits c32vectors (complex samples)
    p2s_complex = pdu.pdu_to_tagged_stream(gr.types.complex_t, "packet_len")
    
    # Receiver
    depkt = depacketizer(config_path=config_path)
    msg_debug = blocks.message_debug()
    
    # The Wire (Direct connection)
    tb.msg_connect((pkt, "out"), (p2s_complex, "pdus"))
    tb.connect(p2s_complex, depkt)
    tb.msg_connect((depkt, "out"), (msg_debug, "store"))
    
    print("[*] Starting Flowgraph...")
    tb.start()
    
    test_payload = b"AUDIT_PULSE_12345"
    print(f"[*] Injecting Test PDU: {test_payload}")
    pkt.handle_msg(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(test_payload), list(test_payload))))
    
    # Wait for recovery
    success = False
    start_time = time.time()
    while time.time() - start_time < 2.0:
        if msg_debug.num_messages() > 0:
            recv = bytes(pmt.u8vector_elements(pmt.cdr(msg_debug.get_message(0))))
            print(f"\033[92m[SUCCESS] Recovered Data: {recv}\033[0m")
            success = True
            break
        time.sleep(0.1)
    
    tb.stop()
    tb.wait()
    
    if not success:
        print("\033[91m[FAILURE] The digital wire is broken. The issue is in the Python math, not the USRP.\033[0m")
    
    return success

if __name__ == "__main__":
    run_wire_audit()
