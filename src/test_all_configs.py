#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Automated Configuration Stress Tester (v15.1)

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

def run_single_test(config_dict, test_name):
    """Runs a digital loopback test for a specific configuration."""
    print(f"--- [TEST] {test_name} ---")
    
    # Save temp config for the blocks to load
    tmp_config = "tmp_test_config.yaml"
    with open(tmp_config, 'w') as f:
        yaml.dump(config_dict, f)
    
    tb = gr.top_block()
    # Note: depacketizer in v11.7+ handles bits directly (out_sig=None)
    pkt = packetizer(config_path=tmp_config, src_id=1)
    depkt = depacketizer(config_path=tmp_config, src_id=1, ignore_self=False)
    p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
    msg_debug = blocks.message_debug()
    
    # Bridge: Packetizer(PDU) -> P2S(Stream) -> Depacketizer(Stream)
    tb.msg_connect((pkt, "out"), (p2s, "pdus"))
    tb.connect(p2s, depkt)
    tb.msg_connect((depkt, "out"), (msg_debug, "store"))
    
    tb.start()
    test_payload = f"OPAL_STRESS_{test_name}".encode()
    pkt.handle_msg(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(test_payload), list(test_payload))))
    
    success = False
    start_time = time.time()
    while time.time() - start_time < 1.0: # 1 second is plenty for digital loopback
        if msg_debug.num_messages() > 0:
            recv_payload = bytes(pmt.u8vector_elements(pmt.cdr(msg_debug.get_message(0))))
            if test_payload in recv_payload:
                success = True; break
        time.sleep(0.05)
    
    tb.stop(); tb.wait()
    if os.path.exists(tmp_config): os.remove(tmp_config)
    
    print(f"Result: {'\033[92mSUCCESS\033[0m' if success else '\033[91mFAILURE\033[0m'}\n")
    return success

def main():
    base_cfg = {
        'mission': {'id': 'LEVEL_1_SOFT_LINK'},
        'physical': {'modulation': 'GFSK', 'samples_per_symbol': 10, 'freq_dev': 25000, 'ghost_mode': False},
        'link_layer': {'frame_size': 120, 'use_fec': True, 'fec_type': 'RS1511', 'use_interleaving': True, 'interleaver_rows': 15, 'use_whitening': True, 'use_nrzi': True, 'use_comsec': False, 'crc_type': 'CRC16'},
        'mac_layer': {'arq_enabled': False},
        'dsss': {'enabled': False, 'type': 'Barker', 'spreading_factor': 11},
        'hopping': {'enabled': False},
        'hardware': {'samp_rate': 2000000}
    }
    
    test_suite = [
        ("Baseline (GFSK + FEC)", {}),
        ("Tactical (L6 Syncword)", {'mission': {'id': 'LEVEL_6_LINK16'}}),
        ("Heavy FEC (RS3115)", {'link_layer': {'frame_size': 120, 'use_fec': True, 'fec_type': 'RS3115', 'use_interleaving': True, 'interleaver_rows': 15, 'use_whitening': True, 'use_nrzi': True, 'use_comsec': False, 'crc_type': 'CRC16'}}),
        ("CCSK Spreading", {'mission': {'id': 'LEVEL_6_LINK16'}, 'dsss': {'enabled': True, 'type': 'CCSK', 'spreading_factor': 32}}),
        ("Barker Spreading", {'dsss': {'enabled': True, 'type': 'Barker', 'spreading_factor': 11}}),
        ("Long Frames (1024)", {'link_layer': {'frame_size': 1024, 'use_fec': True, 'fec_type': 'RS1511', 'use_interleaving': True, 'interleaver_rows': 32, 'use_whitening': True, 'use_nrzi': True, 'use_comsec': False, 'crc_type': 'CRC16'}}),
        ("MSK Waveform", {'physical': {'modulation': 'MSK'}}),
        ("GMSK Waveform", {'physical': {'modulation': 'GMSK'}}),
        ("DQPSK Waveform", {'physical': {'modulation': 'DQPSK'}}),
    ]
    
    results = []
    print("\n" + "="*40)
    print("   OPAL VANGUARD v15.0 REGRESSION SUITE   ")
    print("="*40 + "\n")
    
    for name, overrides in test_suite:
        cfg = base_cfg.copy()
        # Deep update for nested dicts
        for k, v in overrides.items():
            if isinstance(v, dict) and k in cfg: cfg[k].update(v)
            else: cfg[k] = v
        results.append(run_single_test(cfg, name))

    passed = sum(results); total = len(results)
    print("="*40)
    print(f"FINAL REPORT: {passed}/{total} Passed")
    print("="*40 + "\n")
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
