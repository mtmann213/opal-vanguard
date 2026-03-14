#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - PHY Layer Timing & Tag Validation (v1.0)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, digital, pdu
import pmt
import time
import yaml

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from packetizer import packetizer

class TagMonitor(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, "TagMonitor", in_sig=[np.complex64], out_sig=[np.complex64])
        self.packet_count = 0
        self.last_packet_len = 0
        self.samples_received = 0
        self.burst_active = False
        self.errors = []

    def work(self, i, o):
        in0 = i[0]
        n = len(in0)
        
        tags = self.get_tags_in_window(0, 0, n)
        for tag in tags:
            key = pmt.symbol_to_string(tag.key)
            if key == "packet_len":
                val = pmt.to_long(tag.value)
                print(f"[MONITOR] Found packet_len tag: {val} samples at offset {tag.offset}")
                
                if self.burst_active:
                    # Previous burst didn't finish?
                    self.errors.append(f"Overlapping burst detected! Samples rx: {self.samples_received} vs Expected: {self.last_packet_len}")
                
                self.last_packet_len = val
                self.samples_received = 0
                self.burst_active = True
                self.packet_count += 1

        if self.burst_active:
            self.samples_received += n
            if self.samples_received >= self.last_packet_len:
                # Note: We don't check for exact match here because modulators 
                # might produce more samples than the tag value, which is fine 
                # as long as the tag value isn't LONGER than the samples (under-run).
                self.burst_active = False
                self.samples_received = 0

        o[0][:] = in0
        return n

def test_phy_timing(mod_type, sps=10):
    print(f"\n=== Testing PHY Timing: {mod_type} (SPS: {sps}) ===")
    
    config = {
        'physical': {'modulation': mod_type, 'samples_per_symbol': sps, 'freq_dev': 25000},
        'link_layer': {'frame_size': 120, 'use_fec': False, 'use_whitening': False, 'use_interleaving': False, 'use_nrzi': False},
        'mission': {'id': 'TIMING_TEST'}
    }
    
    # Save temp config for the packetizer to load
    with open("tmp_phy_config.yaml", 'w') as f: yaml.dump(config, f)
    
    tb = gr.top_block()
    pkt = packetizer(config_path="tmp_phy_config.yaml")
    p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
    mult_len = blocks.tagged_stream_multiply_length(gr.sizeof_gr_complex, "packet_len", sps)
    monitor = TagMonitor()
    sink = blocks.null_sink(gr.sizeof_gr_complex)
    
    # Setup Modulator
    if mod_type in ["GFSK", "MSK", "GMSK"]:
        sens = (2.0 * np.pi * 25000) / 2000000
        bt = 0.5 if mod_type == "MSK" else 0.35
        mod = digital.gfsk_mod(sps, sens, bt, False, False, False)
    elif mod_type == "DBPSK":
        mod = digital.psk_mod(2, samples_per_symbol=sps, differential=True)
    elif mod_type == "DQPSK":
        mod = digital.psk_mod(4, differential=True, samples_per_symbol=sps)
    else:
        print(f"Unsupported mod: {mod_type}")
        return False

    tb.msg_connect((pkt, "out"), (p2s, "pdus"))
    # The crucial chain: p2s -> mod -> mult_len -> sink
    tb.connect(p2s, mod, mult_len, monitor, sink)
    
    tb.start()
    # Send a small packet
    test_msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(10, [0]*10))
    pkt.handle_msg(test_msg)
    
    time.sleep(0.2)
    tb.stop(); tb.wait()
    
    if os.path.exists("tmp_phy_config.yaml"): os.remove("tmp_phy_config.yaml")
    
    if monitor.errors:
        for err in monitor.errors: print(f"\033[91m[ERROR] {err}\033[0m")
        return False
    else:
        print(f"\033[92m[PASS] {mod_type} Timing Validated.\033[0m")
        return True

if __name__ == "__main__":
    mods = ["GFSK", "MSK", "DBPSK", "DQPSK"]
    results = []
    for m in mods:
        try: results.append(test_phy_timing(m))
        except Exception as e:
            print(f"\033[91m[CRASH] {m}: {e}\033[0m")
            results.append(False)
    
    print("\n" + "="*40)
    print(f"PHY TIMING REPORT: {sum(results)}/{len(results)} Passed")
    print("="*40)
    sys.exit(0 if all(results) else 1)
