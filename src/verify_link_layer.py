#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Bit-Perfect Link Layer Regression (v1.0)

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

def run_logic_test(name, overrides):
    print(f"[*] Testing Logic: {name}")
    cfg = {
        'mission': {'id': 'LOGIC_TEST'},
        'physical': {'modulation': 'GFSK', 'samples_per_symbol': 10},
        'link_layer': {'frame_size': 120, 'use_fec': False, 'use_interleaving': False, 'use_whitening': False, 'use_nrzi': False, 'use_comsec': False},
        'hardware': {'samp_rate': 2000000}, 'hopping': {'enabled': False}, 'dsss': {'enabled': False}
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and k in cfg: cfg[k].update(v)
        else: cfg[k] = v

    tmp_file = f"tmp_logic_{time.time()}.yaml"
    with open(tmp_file, 'w') as f: yaml.dump(cfg, f)
    
    tb = gr.top_block()
    pkt = packetizer(config_path=tmp_file)
    depkt = depacketizer(config_path=tmp_file)
    p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
    msg_debug = blocks.message_debug()
    
    tb.msg_connect((pkt, "out"), (p2s, "pdus"))
    # Direct Bit Path: p2s -> depkt (No modulator delay or noise)
    tb.connect(p2s, depkt)
    tb.msg_connect((depkt, "out"), (msg_debug, "store"))
    
    tb.start()
    payload = f"LOGIC_DATA_{name}_{time.time()}".encode()
    pkt.handle_msg(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(payload), list(payload))))
    
    success = False
    start = time.time()
    while time.time() - start < 0.5:
        if msg_debug.num_messages() > 0:
            recv = bytes(pmt.u8vector_elements(pmt.cdr(msg_debug.get_message(0))))
            if payload in recv: success = True; break
        time.sleep(0.01)
    
    tb.stop(); tb.wait()
    if os.path.exists(tmp_file): os.remove(tmp_file)
    print(f"    Result: {'\033[92mSUCCESS\033[0m' if success else '\033[91mFAILURE\033[0m'}")
    return success

if __name__ == "__main__":
    tests = [
        ("Base Frame", {}),
        ("RS1511 FEC", {'link_layer': {'use_fec': True, 'fec_type': 'RS1511'}}),
        ("RS3115 FEC", {'link_layer': {'use_fec': True, 'fec_type': 'RS3115'}}),
        ("Whitening LFSR", {'link_layer': {'use_whitening': True}}),
        ("Matrix Interleave", {'link_layer': {'use_interleaving': True, 'interleaver_rows': 15}}),
        ("NRZI Diff", {'link_layer': {'use_nrzi': True}}),
        ("AES-CTR COMSEC", {'link_layer': {'use_comsec': True, 'comsec_key': '00'*32}}),
        ("Full Secure Stack", {
            'link_layer': {'use_fec': True, 'use_interleaving': True, 'use_whitening': True, 'use_nrzi': True, 'use_comsec': True}
        }),
        ("Giant Frames (1024)", {'link_layer': {'frame_size': 1024, 'interleaver_rows': 32}}),
    ]
    
    results = []
    print("\n=== BIT-PERFECT LINK LAYER REGRESSION ===")
    for name, overrides in tests:
        results.append(run_logic_test(name, overrides))
        
    passed = sum(results); total = len(results)
    print("\n" + "="*40)
    print(f"FINAL LOGIC REPORT: {passed}/{total} Passed")
    print("="*40 + "\n")
    sys.exit(0 if passed == total else 1)
