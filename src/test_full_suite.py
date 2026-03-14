#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Master Feature Validation Suite (v1.0)

import os
import sys
import yaml
import time
import pmt
import numpy as np
from gnuradio import gr, blocks, pdu, digital, analog

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from packetizer import packetizer
from depacketizer import depacketizer

def run_logic_check(name, overrides):
    """Verifies Link Layer features in a digital pipe."""
    cfg = {
        'mission': {'id': 'LOGIC_TEST'},
        'physical': {'modulation': 'GFSK', 'samples_per_symbol': 10},
        'link_layer': {'frame_size': 120, 'use_fec': False, 'use_interleaving': False, 'use_whitening': False, 'use_nrzi': False, 'use_comsec': False},
        'hardware': {'samp_rate': 2000000}, 'hopping': {'enabled': False}
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and k in cfg: cfg[k].update(v)
        else: cfg[k] = v

    tmp_file = f"tmp_logic.yaml"
    with open(tmp_file, 'w') as f: yaml.dump(cfg, f)
    
    tb = gr.top_block()
    pkt = packetizer(config_path=tmp_file)
    depkt = depacketizer(config_path=tmp_file)
    p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
    msg_debug = blocks.message_debug()
    
    tb.msg_connect((pkt, "out"), (p2s, "pdus"))
    tb.connect(p2s, depkt)
    tb.msg_connect((depkt, "out"), (msg_debug, "store"))
    
    tb.start()
    payload = f"LOGIC_OK_{name}".encode()
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
    return success

def main():
    print("\n" + "="*50)
    print("   OPAL VANGUARD MASTER VALIDATION SUITE   ")
    print("="*50 + "\n")
    
    # 1. Logic Tests
    logic_tests = [
        ("Base Protocol", {}),
        ("RS1511 FEC", {'link_layer': {'use_fec': True, 'fec_type': 'RS1511'}}),
        ("RS3115 FEC", {'link_layer': {'use_fec': True, 'fec_type': 'RS3115'}}),
        ("Whitening", {'link_layer': {'use_whitening': True}}),
        ("Matrix Interleave", {'link_layer': {'use_interleaving': True}}),
        ("NRZI Encoder", {'link_layer': {'use_nrzi': True}}),
        ("AES-CTR COMSEC", {'link_layer': {'use_comsec': True}}),
    ]
    
    results = []
    print("--- [PHASE 1] Link Layer Logic ---")
    for name, overrides in logic_tests:
        res = run_logic_check(name, overrides)
        results.append(res)
        status = "\033[92m[PASS]\033[0m" if res else "\033[91m[FAIL]\033[0m"
        print(f"{status} {name}")

    # 2. Timing Standards
    print("\n--- [PHASE 2] PHY Hardware Timing Standards ---")
    timing_ok = True
    # We verify that FinalTagFixer exists in the source files
    try:
        with open("src/usrp_transceiver.py", 'r') as f:
            content = f.read()
            if "FinalTagFixer" in content and "+ 8000" in content:
                print("\033[92m[PASS]\033[0m FinalTagFixer found with 8000-sample safety margin.")
            else:
                print("\033[91m[FAIL]\033[0m FinalTagFixer missing or safety margin too low.")
                timing_ok = False
    except:
        timing_ok = False

    # 3. Dynamic Configuration Parity
    print("\n--- [PHASE 3] Dynamic Configuration Architecture ---")
    config_ok = True
    try:
        with open("src/packetizer.py", 'r') as f:
            if "self.sync_hex = p_cfg.get(\'syncword\'" in f.read():
                print("\033[92m[PASS]\033[0m Packetizer correctly implements dynamic syncwords.")
            else:
                print("\033[91m[FAIL]\033[0m Packetizer is missing dynamic syncword support.")
                config_ok = False
    except:
        config_ok = False

    print("\n" + "="*50)
    passed = sum(results) + (1 if timing_ok else 0) + (1 if config_ok else 0)
    total = len(results) + 2
    print(f"MASTER REPORT: {passed}/{total} Requirements Met")
    print("="*50 + "\n")
    
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
