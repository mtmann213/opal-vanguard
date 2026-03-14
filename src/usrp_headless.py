#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Headless USRP Node (v15.8.15 Restoration)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, digital, uhd, pdu, filter
import pmt
import time
import yaml
import argparse

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer
from hop_generator_tod import tod_hop_generator
from hop_generator_aes import aes_hop_generator
from session_manager import session_manager

class FinalTagFixer(gr.sync_block):
    """
    v15.8.15: The Tag Gap Resolver.
    Ensures the USRP burst gate stays open long enough for the modulator filter tail.
    """
    def __init__(self, sps):
        gr.sync_block.__init__(self, "FinalTagFixer", in_sig=[np.complex64], out_sig=[np.complex64])
        self.sps = sps
        self.set_tag_propagation_policy(gr.TPP_DONT)

    def work(self, i, o):
        tags = self.get_tags_in_window(0, 0, len(i[0]))
        for tag in tags:
            if pmt.symbol_to_string(tag.key) == "packet_len":
                val = pmt.to_long(tag.value)
                samples = (val * self.sps) if val < 5000 else val
                new_val = samples + 8000
                self.add_item_tag(0, tag.offset, tag.key, pmt.from_long(new_val))
            else:
                self.add_item_tag(0, tag.offset, tag.key, tag.value)
        o[0][:] = i[0]
        return len(i[0])

class OpalVanguardUSRPHeadless(gr.top_block):
    def __init__(self, role="ALPHA", serial="", config_path="mission_configs/level1_soft_link.yaml"):
        gr.top_block.__init__(self, f"Opal Vanguard - {role}")
        self.role = role
        print(f"[{self.role}] Loading config from {config_path}...")
        
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
            
        hcfg = self.cfg['hopping']
        hw_cfg = self.cfg['hardware']
        p_cfg = self.cfg['physical']

        self.samp_rate = hw_cfg.get('samp_rate', 2000000)
        self.center_freq = p_cfg.get('center_freq', 915000000)

        print(f"[{self.role}] Initializing USRP with serial: {serial}")
        try:
            args = hw_cfg['args']
            if serial: args += f",serial={serial}"
            self.usrp_sink = uhd.usrp_sink(args, uhd.stream_args(cpu_format="fc32", channels=[0]), "packet_len")
            self.usrp_source = uhd.usrp_source(args, uhd.stream_args(cpu_format="fc32", channels=[0]))
            
            for dev in [self.usrp_sink, self.usrp_source]:
                dev.set_samp_rate(self.samp_rate)
                dev.set_center_freq(self.center_freq, 0)
            self.usrp_sink.set_gain(hw_cfg['tx_gain'], 0)
            self.usrp_source.set_gain(hw_cfg['rx_gain'], 0)
            print(f"[{self.role}] USRP frequencies and gains set.")
        except Exception as e:
            print(f"FATAL: USRP ERROR: {e}"); sys.exit(1)

        print(f"[{self.role}] Setting up session managers...")
        sid = 1 if self.role == "ALPHA" else 2
        self.session_a = session_manager(initial_seed=hcfg['initial_seed'], config_path=config_path)
        self.session_b = session_manager(initial_seed=hcfg['initial_seed'], config_path=config_path)
        
        self.pkt_a = packetizer(config_path=config_path, src_id=sid)
        self.depkt_b = depacketizer(config_path=config_path, src_id=sid, ignore_self=True)

        print(f"[{self.role}] Setting up modulation ({p_cfg.get('modulation', 'GFSK')})...")
        self.pdu_src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len("MISSION DATA"), list("MISSION DATA".encode()))), 3000)
        self.p2s_a = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        mod_type = p_cfg.get('modulation', 'GFSK')
        sps = p_cfg.get('samples_per_symbol', 10)
        # v15.8.15: Use FinalTagFixer for reliable hardware gating
        self.tag_fixer = FinalTagFixer(sps)
        
        if mod_type == "DBPSK":
            self.mod_a = digital.psk_mod(2, samples_per_symbol=sps, differential=True)
            self.demod_b = digital.psk_demod(2, samples_per_symbol=sps, differential=True)
        elif mod_type == "DQPSK":
            self.mod_a = digital.psk_mod(4, differential=True, samples_per_symbol=sps, excess_bw=0.35)
            self.demod_b = digital.psk_demod(4, differential=True, samples_per_symbol=sps, excess_bw=0.35)
        else:
            freq_dev = p_cfg.get('freq_dev', 25000)
            sens = (2.0 * np.pi * freq_dev) / self.samp_rate
            self.mod_a = digital.gfsk_mod(sps, sens, 0.35, False, False, False)
            self.demod_b = digital.gfsk_demod(sps, sens, 0.1, 0.5, 0.005, 0.0)

        print(f"[{self.role}] Initializing hop generator...")
        self.hop_ctrl = tod_hop_generator(key=bytes.fromhex(hcfg.get('aes_key', '00'*32)), num_channels=hcfg.get('num_channels', 50), center_freq=self.center_freq, channel_spacing=hcfg.get('channel_spacing', 150000), dwell_ms=hcfg.get('dwell_time_ms', 500))

        print(f"[{self.role}] Setting up RX filters...")
        self.rx_filter = filter.fir_filter_ccf(1, filter.firdes.low_pass(1.0, self.samp_rate, 100e3, 50e3))

        print(f"[{self.role}] Connecting blocks...")
        self.msg_connect((self.pdu_src, "strobe"), (self.session_a, "data_in"))
        self.msg_connect((self.session_a, "pkt_out"), (self.pkt_a, "in"))
        self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
        # v15.8.15: FinalTagFixer placed AFTER mod_a
        self.connect(self.p2s_a, self.mod_a, self.tag_fixer, self.usrp_sink)
        self.connect(self.usrp_source, self.rx_filter, self.demod_b, self.depkt_b)
        self.msg_connect((self.depkt_b, "out"), (self.session_b, "msg_in"))
        self.msg_connect((self.session_b, "pkt_out"), (self.session_a, "msg_in"))

        class UHDHandler(gr.basic_block):
            def __init__(self, parent):
                gr.basic_block.__init__(self, "UHDHandler", None, None); self.parent = parent
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
                self.last_f = 0
            def handle(self, msg):
                try:
                    f = pmt.to_double(pmt.dict_ref(msg, pmt.intern("freq"), pmt.from_double(0)))
                    t = pmt.to_double(pmt.dict_ref(msg, pmt.intern("time"), pmt.from_double(0)))
                    if f > 0 and f != self.last_f:
                        if t > (time.time() + 0.010):
                            cmd_time = uhd.time_spec(t)
                            self.parent.usrp_sink.set_command_time(cmd_time, 0)
                            self.parent.usrp_source.set_command_time(cmd_time, 0)
                            self.parent.usrp_sink.set_center_freq(f, 0)
                            self.parent.usrp_source.set_center_freq(f, 0)
                            self.parent.usrp_sink.clear_command_time(0)
                            self.parent.usrp_source.clear_command_time(0)
                        else:
                            self.parent.usrp_sink.set_center_freq(f, 0)
                            self.parent.usrp_source.set_center_freq(f, 0)
                        self.last_f = f
                except: pass
            def work(self, i, o): return 0
        
        self.uhd_h = UHDHandler(self); self.msg_connect((self.hop_ctrl, "freq"), (self.uhd_h, "msg"))

        class DiagPrinter(gr.basic_block):
            def __init__(self, role):
                gr.basic_block.__init__(self, "DiagPrinter", None, None); self.role = role
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                try:
                    ok_pmt = pmt.dict_ref(msg, pmt.intern("crc_ok"), pmt.PMT_F)
                    if pmt.is_true(ok_pmt):
                        repairs = pmt.to_long(pmt.dict_ref(msg, pmt.intern("fec_repairs"), pmt.from_long(0)))
                        conf = pmt.to_double(pmt.dict_ref(msg, pmt.intern("confidence"), pmt.from_double(0)))
                        print(f"[{self.role}] \033[92mCRC PASS\033[0m | LQI: {conf:.1f}% | FEC: {repairs}")
                except: pass
        
        self.dp = DiagPrinter(role); self.msg_connect((self.depkt_b, "diagnostics"), (self.dp, "msg"))
        
        class DataPrinter(gr.basic_block):
            def __init__(self, role):
                gr.basic_block.__init__(self, "DataPrinter", None, None); self.role = role
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                try:
                    payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
                    print(f"[{self.role}] RX DATA: {payload}")
                except Exception as e:
                    print(f"[{self.role}] Error decoding RX data: {e}")

        self.rx_prnt = DataPrinter(role); self.msg_connect((self.depkt_b, "out"), (self.rx_prnt, "msg"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", default="ALPHA", choices=["ALPHA", "BRAVO"])
    parser.add_argument("--serial", default="")
    parser.add_argument("--config", default="mission_configs/level1_soft_link.yaml")
    args = parser.parse_args()
    tb = OpalVanguardUSRPHeadless(role=args.role, serial=args.serial, config_path=args.config)
    tb.start()
    print(f"Opal Vanguard Headless Node - {args.role} [{args.serial}] Started.")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        tb.stop(); tb.wait()

if __name__ == "__main__":
    main()
