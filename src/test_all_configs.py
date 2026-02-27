#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Automated Configuration Stress Tester

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
    
    with open("config.yaml", 'w') as f:
        yaml.dump(config_dict, f)
    
    tb = gr.top_block()
    pkt = packetizer(config_path="config.yaml")
    depkt = depacketizer(config_path="config.yaml")
    p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
    unp = blocks.unpack_k_bits_bb(8) 
    msg_debug = blocks.message_debug()
    
    tb.msg_connect((pkt, "out"), (p2s, "pdus"))
    tb.connect(p2s, unp)
    tb.connect(unp, depkt)
    tb.msg_connect((depkt, "out"), (msg_debug, "store"))
    
    tb.start()
    test_payload = f"Opal:{test_name}".encode()
    pkt.handle_msg(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(test_payload), list(test_payload))))
    
    success = False
    start_time = time.time()
    while time.time() - start_time < 3.0: 
        if msg_debug.num_messages() > 0:
            recv_payload = bytes(pmt.u8vector_elements(pmt.cdr(msg_debug.get_message(0))))
            if test_payload in recv_payload:
                success = True; break
        time.sleep(0.1)
    
    tb.stop(); tb.wait()
    print(f"Result: {'SUCCESS' if success else 'FAILURE'}\n")
    return success

def main():
    base_cfg = {
        'mission': {'id': 'AUTO_TEST'},
        'physical': {'samp_rate': 2000000, 'center_freq': 915000000, 'modulation': 'GFSK', 'mod_index': 1.0, 'samples_per_symbol': 8},
        'dsss': {'enabled': False, 'spreading_factor': 31, 'chipping_code': [1]*31},
        'hopping': {'enabled': False, 'sync_mode': 'TOD', 'type': 'AES', 'aes_key': '000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f', 'dwell_time_ms': 200, 'lookahead_ms': 10, 'num_channels': 50, 'channel_spacing': 150000, 'initial_seed': 0xACE},
        'hardware': {'args': 'type=b200', 'samp_rate': 2000000, 'tx_gain': 50, 'rx_gain': 50, 'tx_antenna': 'TX/RX', 'rx_antenna': 'TX/RX'}
    }
    tests = [
        ("Minimalist", {'use_fec': False, 'use_interleaving': False, 'use_whitening': False, 'use_manchester': False, 'use_nrzi': False, 'crc_type': 'CRC16'}),
        ("FEC", {'use_fec': True, 'use_interleaving': False, 'use_whitening': False, 'use_manchester': False, 'use_nrzi': False, 'crc_type': 'CRC16'}),
        ("Interleaving", {'use_fec': False, 'use_interleaving': True, 'use_whitening': False, 'use_manchester': False, 'use_nrzi': False, 'crc_type': 'CRC16'}),
        ("Whitening", {'use_fec': False, 'use_interleaving': False, 'use_whitening': True, 'use_manchester': False, 'use_nrzi': False, 'crc_type': 'CRC16'}),
        ("NRZI", {'use_fec': False, 'use_interleaving': False, 'use_whitening': False, 'use_manchester': False, 'use_nrzi': True, 'crc_type': 'CRC16'}),
        ("Manchester", {'use_fec': False, 'use_interleaving': False, 'use_whitening': False, 'use_manchester': True, 'use_nrzi': False, 'crc_type': 'CRC16'}),
        ("CRC32", {'use_fec': True, 'use_interleaving': True, 'use_whitening': True, 'use_manchester': False, 'use_nrzi': True, 'crc_type': 'CRC32'}),
        ("Full Hardening", {'use_fec': True, 'use_interleaving': True, 'use_whitening': True, 'use_manchester': False, 'use_nrzi': True, 'crc_type': 'CRC16'}),
    ]
    results = []
    for name, l_cfg in tests:
        cfg = base_cfg.copy(); cfg['link_layer'] = l_cfg
        results.append(run_single_test(cfg, name))
    cfg = base_cfg.copy()
    cfg['link_layer'] = {'use_fec': True, 'use_interleaving': True, 'use_whitening': True, 'use_manchester': False, 'use_nrzi': True, 'crc_type': 'CRC16'}
    cfg['dsss'] = {'enabled': True, 'spreading_factor': 31, 'chipping_code': [1]*31}
    results.append(run_single_test(cfg, "DSSS Mode"))
    print("="*30); print(f"FINAL REPORT: {sum(results)}/{len(results)} Passed"); print("="*30)
    sys.exit(0 if all(results) else 1)

if __name__ == "__main__":
    main()
