#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - USRP Headless Transceiver (v19.49)

import os
import sys
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

from gnuradio import gr, blocks, analog, digital, filter, uhd, pdu
import pmt
import yaml
import argparse
import time

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from session_manager import session_manager
from packetizer import packetizer
from depacketizer import depacketizer

class FinalTagFixer(gr.sync_block):
    def __init__(self, sps):
        gr.sync_block.__init__(self, "FinalTagFixer", in_sig=[np.complex64], out_sig=[np.complex64])
        self.sps = sps
        self.set_tag_propagation_policy(gr.TPP_DONT)
    def work(self, i, o):
        tags = self.get_tags_in_window(0, 0, len(i[0]))
        for tag in tags:
            key = pmt.symbol_to_string(tag.key)
            if key in ["bit_count", "bit_len"]:
                # v19.50: Pure Scaling + 320 sample offset (32 bits @ SPS=10)
                # to compensate for the modulator filter delay.
                new_val = pmt.from_long(pmt.to_long(tag.value) * self.sps)
                self.add_item_tag(0, self.nitems_written(0) + 320, pmt.intern("packet_len"), new_val)
            elif key == "tx_sob":
                self.add_item_tag(0, self.nitems_written(0) + 320, tag.key, tag.value)
        o[0][:] = i[0]
        return len(i[0])

class OpalVanguardUSRPHeadless(gr.top_block):
    def __init__(self, role="ALPHA", serial="", config_path="mission_configs/level1_soft_link.yaml"):
        gr.top_block.__init__(self, f"Opal Vanguard - {role}")
        self.role = role
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
            
        hcfg = self.cfg['hopping']
        hw_cfg = self.cfg['hardware']
        p_cfg = self.cfg['physical']
        l_cfg = self.cfg['link_layer']
        
        self.samp_rate = p_cfg.get('samp_rate', hw_cfg.get('samp_rate', 2000000))
        self.center_freq = p_cfg.get('center_freq', 915000000)

        try:
            self.usrp_sink = uhd.usrp_sink(hw_cfg['args'] + (f",serial={serial}" if serial else ""), 
                                          uhd.stream_args(cpu_format="fc32", channels=[0]), "packet_len")
            self.usrp_source = uhd.usrp_source(hw_cfg['args'] + (f",serial={serial}" if serial else ""), 
                                            uhd.stream_args(cpu_format="fc32", channels=[0]))
            for dev in [self.usrp_sink, self.usrp_source]:
                dev.set_samp_rate(self.samp_rate)
                dev.set_center_freq(self.center_freq, 0)
            self.usrp_sink.set_gain(hw_cfg['tx_gain'], 0)
            self.usrp_source.set_gain(hw_cfg['rx_gain'], 0)
        except Exception as e:
            print(f"FATAL: USRP ERROR: {e}"); sys.exit(1)

        sid = 1 if role == "ALPHA" else 2
        self.session = session_manager(initial_seed=hcfg.get('initial_seed', 0xACE), config_path=config_path)
        self.pkt_a = packetizer(config_path=config_path, src_id=sid)
        self.depkt_b = depacketizer(config_path=config_path, src_id=sid, ignore_self=True)
        
        self.mac_strobe = blocks.message_strobe(pmt.PMT_T, 1000)
        hb_payload = f"PING FROM {role}".encode()
        hb_msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(hb_payload), list(hb_payload)))
        strobe_ms = 1000 if ("LEVEL_6" in config_path or "LEVEL_7" in config_path) else 200
        self.pdu_src = blocks.message_strobe(hb_msg, strobe_ms)
        
        self.p2s_a = pdu.pdu_to_tagged_stream(gr.types.byte_t, "bit_count")
        
        mod_type = p_cfg.get('modulation', 'DBPSK')
        sps = p_cfg.get('samples_per_symbol', 10)
        self.tag_fixer = FinalTagFixer(sps)
        
        if mod_type == "DBPSK":
            self.mod_a = digital.psk_mod(2, samples_per_symbol=sps, differential=True)
            self.demod_b = digital.psk_demod(2, samples_per_symbol=sps, differential=True)
        elif mod_type in ["GFSK", "MSK", "GMSK"]:
            bit_rate = self.samp_rate / sps
            sens = (2.0 * np.pi * (bit_rate/4.0)) / self.samp_rate
            self.mod_a = digital.gfsk_mod(samples_per_symbol=sps, sensitivity=sens, bt=0.35)
            self.demod_b = digital.gfsk_demod(samples_per_symbol=sps, sensitivity=sens, gain_mu=0.1, mu=0.5, omega_relative_limit=0.005, freq_error=0.0)
        else:
            self.mod_a = digital.psk_mod(2, samples_per_symbol=sps)
            self.demod_b = digital.psk_demod(2, samples_per_symbol=sps)

        self.rx_filter = filter.fir_filter_ccf(1, filter.firdes.low_pass(1.0, self.samp_rate, 250e3, 50e3))

        # Connections
        self.msg_connect((self.mac_strobe, "strobe"), (self.session, "heartbeat"))
        self.msg_connect((self.pdu_src, "strobe"), (self.session, "data_in"))
        self.msg_connect((self.session, "pkt_out"), (self.pkt_a, "in"))
        self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
        
        self.connect(self.p2s_a, self.mod_a, self.tag_fixer, self.usrp_sink)
        self.connect(self.usrp_source, self.rx_filter, self.demod_b, self.depkt_b)
        
        self.msg_connect((self.depkt_b, "out"), (self.session, "msg_in"))
        self.msg_connect((self.depkt_b, "diagnostics"), (self.session, "msg_in"))

        class UHDHandler(gr.basic_block):
            def __init__(self, sink, source):
                gr.basic_block.__init__(self, "UHDHandler", None, None); self.sink, self.source = sink, source
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                try: 
                    f = pmt.to_double(msg); self.sink.set_center_freq(f); self.source.set_center_freq(f)
                except: pass
        self.uhd_h = UHDHandler(self.usrp_sink, self.usrp_source)

        class TerminalPrinter(gr.basic_block):
            def __init__(self, role):
                gr.basic_block.__init__(self, "TerminalPrinter", None, None); self.role = role
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                try:
                    if pmt.is_pair(msg):
                        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
                        print(f"\033[92m[{self.role}] RX DATA: {payload}\033[0m", flush=True)
                    elif pmt.is_dict(msg):
                        d = {pmt.symbol_to_string(k): pmt.to_python(v) for k,v in pmt.dict_to_alist(msg)}
                        if d.get('crc_ok'):
                            print(f"[{self.role}] CRC PASS | FEC: {d.get('fec_corrections', 0)}", flush=True)
                except: pass
        self.tp = TerminalPrinter(role)
        self.msg_connect((self.depkt_b, "out"), (self.tp, "msg"))
        self.msg_connect((self.depkt_b, "diagnostics"), (self.tp, "msg"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", default="ALPHA", choices=["ALPHA", "BRAVO"])
    parser.add_argument("--serial", default="")
    parser.add_argument("--config", default="mission_configs/level1_soft_link.yaml")
    args = parser.parse_args()
    tb = OpalVanguardUSRPHeadless(role=args.role, serial=args.serial, config_path=args.config)
    tb.start()
    print(f"--- [OPAL VANGUARD {args.role} HEADLESS START] ---")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        tb.stop(); tb.wait()

if __name__ == '__main__': main()
