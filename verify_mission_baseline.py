#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Mission Baseline Verifier (Levels 1-5)

import os
import sys
import yaml
import time
import pmt
from gnuradio import gr, blocks, pdu

# Add src to path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from packetizer import packetizer
from depacketizer import depacketizer

def run_mission_test(config_path):
    """Runs a digital loopback test for a specific mission configuration file."""
    level_name = os.path.basename(config_path)
    print(f"--- [TESTING BASELINE] {level_name} ---")
    
    try:
        tb = gr.top_block()
        pkt = packetizer(config_path=config_path, src_id=0)
        # We need to manually set comsec_key if enabled, normally handled by usrp_transceiver
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f)
        
        depkt = depacketizer(config_path=config_path, src_id=0, ignore_self=False)
        
        if cfg.get('link_layer', {}).get('use_comsec', False):
            key = bytes.fromhex(cfg['link_layer'].get('comsec_key', '00'*32))
            pkt.use_comsec = True
            pkt.comsec_key = key
            depkt.use_comsec = True
            depkt.comsec_key = key
            print("  [COMSEC ENABLED]")

        p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        msg_debug = blocks.message_debug()
        bit_sink = blocks.null_sink(gr.sizeof_char) # Connect bitstream output
        
        tb.msg_connect((pkt, "out"), (p2s, "pdus"))
        tb.connect(p2s, depkt)
        tb.connect(depkt, bit_sink) # Bitstream sink
        tb.msg_connect((depkt, "out"), (msg_debug, "store"))
        
        tb.start()
        test_payload = f"BASELINE_VERIFY:{level_name}".encode()
        pkt.handle_msg(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(test_payload), list(test_payload))))
        
        success = False
        start_time = time.time()
        while time.time() - start_time < 2.0: 
            if msg_debug.num_messages() > 0:
                recv_payload = bytes(pmt.u8vector_elements(pmt.cdr(msg_debug.get_message(0))))
                if test_payload in recv_payload:
                    success = True; break
            time.sleep(0.1)
        
        tb.stop(); tb.wait()
        print(f"Result: {'PASS' if success else 'FAIL'}\n")
        return success
    except Exception as e:
        print(f"ERROR during {level_name}: {e}")
        return False

def main():
    levels = [
        "mission_configs/level1_soft_link.yaml",
        "mission_configs/level2_repairable.yaml",
        "mission_configs/level3_resilient.yaml",
        "mission_configs/level4_stealth.yaml",
        "mission_configs/level5_blackout.yaml"
    ]
    
    results = []
    print("==========================================")
    print("   OPAL VANGUARD: BASELINE SAFETY CHECK   ")
    print("==========================================")
    
    for lvl in levels:
        if os.path.exists(lvl):
            results.append(run_mission_test(lvl))
        else:
            print(f"MISSING CONFIG: {lvl}")
            results.append(False)

    passed = sum(results)
    total = len(results)
    print("="*42)
    print(f"FINAL REPORT: {passed}/{total} LEVELS STABLE")
    print("="*42)

    if passed == total:
        print("\n[SAFEGUARD] ALL BASELINE LEVELS VERIFIED. READY FOR LEVEL 6.")
        sys.exit(0)
    else:
        print("\n[CRITICAL] REGRESSION DETECTED IN BASELINE. DO NOT PROCEED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
