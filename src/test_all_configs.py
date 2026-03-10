#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Automated Configuration Stress Tester (v15.1)

import os
import sys
import yaml
import time
import pmt
import copy
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
    # Increase buffer size for heavy expansion modes (CCSK)
    tb.set_max_noutput_items(131072)
    
    # Note: depacketizer in v11.7+ handles bits directly (out_sig=None)
    pkt = packetizer(config_path=tmp_config, src_id=1)
    depkt = depacketizer(config_path=tmp_config, src_id=1, ignore_self=False)
    p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
    msg_debug = blocks.message_debug()
    
    # Bridge: Packetizer(PDU) -> P2S(Stream) -> Depacketizer(Stream)
    tb.msg_connect((pkt, "out"), (p2s, "pdus"))
    tb.connect(p2s, depkt)
    tb.msg_connect((depkt, "out"), (msg_debug, "store"))
    
    # Aggressive buffer allocation for heavy expansion (CCSK)
    for b in [pkt, p2s, depkt]:
        try: 
            b.set_max_output_buffer(262144)
            b.set_min_noutput_items(1)
        except: pass
    
    tb.start()
    test_payload = config_dict.get('payload_override', f"OPAL_STRESS_{test_name}".encode())
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
        'physical': {'modulation': 'GFSK', 'samples_per_symbol': 10, 'freq_dev': 25000, 'ghost_mode': False, 'preamble_len': 64},
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
        ("CSS Waveform", {'physical': {'modulation': 'CSS', 'samples_per_symbol': 128}}),
        ("Hardened Mode (TRANSEC)", {'link_layer': {'use_comsec': True, 'use_transec': True, 'use_anti_replay': True}}),
        # New 9 Tests for 18-Point Compliance
        ("Extreme Payload (Empty)", {'payload_override': b''}),
        ("Extreme Payload (Max)", {'link_layer': {'frame_size': 900}}),
        ("High Speed (SPS=4)", {'physical': {'samples_per_symbol': 4}}),
        ("Long Distance (SPS=20)", {'physical': {'samples_per_symbol': 20}}),
        ("Dual: FEC + CCSK", {'link_layer': {'frame_size': 30, 'use_fec': True}, 'dsss': {'enabled': True, 'type': 'CCSK', 'spreading_factor': 32}}),
        ("Dual: FEC + Interleaving + NRZI", {'link_layer': {'frame_size': 30, 'use_fec': True, 'use_nrzi': True, 'use_interleaving': True}}),
        ("GMSK + Barker", {'physical': {'modulation': 'GMSK'}, 'dsss': {'enabled': True, 'type': 'Barker'}}),
        ("DQPSK + RS3115", {'physical': {'modulation': 'DQPSK'}, 'link_layer': {'use_fec': True, 'fec_type': 'RS3115'}}),
        ("L8 Advanced Combo", {'mission': {'id': 'LEVEL_8_ADVANCED'}, 'physical': {'modulation': 'GMSK'}, 'link_layer': {'use_interleaving': True, 'use_whitening': True}}),
    ]
    
    results = []
    print("\n" + "="*40)
    print("   OPAL VANGUARD v15.0 REGRESSION SUITE   ")
    print("="*40 + "\n")
    
    for name, overrides in test_suite:
        cfg = copy.deepcopy(base_cfg)
        # Deep update for nested dicts
        for k, v in overrides.items():
            if isinstance(v, dict) and k in cfg: cfg[k].update(v)
            else: cfg[k] = v
        results.append(run_single_test(cfg, name))
        time.sleep(0.1) # Let scheduler breathe between tests

    passed = sum(results); total = len(results)
    print("="*40)
    print(f"FINAL REPORT: {passed}/{total} Passed")
    print("="*40 + "\n")
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
