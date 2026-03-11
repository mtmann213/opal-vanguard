#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Deep Logic Probe (Diagnostic v1.0)

import sys
import os
import numpy as np
import pmt
import struct
import yaml

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer
from session_manager import session_manager

def run_probe(config_path):
    print(f"\n=== [DIAGNOSTIC PROBE: {config_path}] ===")
    
    # 1. Initialize Blocks
    # Node ALPHA (1) sending to Node BRAVO (2)
    pkt = packetizer(config_path=config_path, src_id=1)
    depkt = depacketizer(config_path=config_path, src_id=2, ignore_self=True)
    session = session_manager(config_path=config_path)
    
    # 2. Simulate a Heartbeat Request
    print("[1/4] Generating Heartbeat...")
    test_payload = b"PING FROM PROBE"
    msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(test_payload), list(test_payload)))
    
    # 3. Step: Session Manager
    # We'll manually trigger the packet creation logic
    print("[2/4] Session Manager processing...")
    # Add sequence metadata like the real session manager does
    meta = pmt.make_dict()
    meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(0)) # DATA
    meta = pmt.dict_add(meta, pmt.intern("seq"), pmt.from_long(99))
    pdu_to_pkt = pmt.cons(meta, pmt.init_u8vector(len(test_payload), list(test_payload)))
    
    # 4. Step: Packetizer
    print("[3/4] Packetizer encoding...")
    encoded_pdu = None
    def capture_pkt(port, msg):
        nonlocal encoded_pdu
        encoded_pdu = msg
    
    pkt.message_port_pub = capture_pkt
    pkt.handle_msg(pdu_to_pkt)
    
    if encoded_pdu is None:
        print("!! FAIL: Packetizer produced NO OUTPUT.")
        return
    
    # Packetizer outputs bit-unpacked U8 vectors with metadata
    raw_bits = list(pmt.u8vector_elements(pmt.cdr(encoded_pdu)))
    meta = pmt.car(encoded_pdu)
    sync_len = 64 if "level6" in config_path else 32
    preamble_len = 512
    
    # Strip Preamble and Syncword to simulate the Depacketizer's 'COLLECT' state input
    data_bits = raw_bits[preamble_len + sync_len:]
    bits_np = np.array(data_bits, dtype=np.uint8)
    bytes_np = np.packbits(bits_np, bitorder='big')
    print(f"      Encoded Payload Section: {len(bytes_np)} bytes")
    
    # 5. Step: Depacketizer
    print("[4/4] Depacketizer decoding...")
    decoded_payload = None
    def capture_rx(port, msg):
        nonlocal decoded_payload
        if pmt.is_pair(msg):
            decoded_payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
    
    depkt.message_port_pub = capture_rx
    
    # Mock the GNU Radio consume method
    def mock_consume(i, n): pass
    depkt.consume = mock_consume
    
    # Feed the full bitstream (including preamble and syncword) into the real state machine
    depkt.general_work([raw_bits], [])
    
    if decoded_payload:
        print(f"[*] SUCCESS: Recovered Payload: {decoded_payload}")
    else:
        print("!! FAIL: Depacketizer failed to recover the message.")

if __name__ == "__main__":
    configs = [
        "mission_configs/level1_soft_link.yaml",
        "mission_configs/level5_blackout.yaml",
        "mission_configs/level6_link16.yaml"
    ]
    for cfg in configs:
        try:
            run_probe(cfg)
        except Exception as e:
            print(f"!! CRASH in {cfg}: {e}")
            import traceback
            traceback.print_exc()
