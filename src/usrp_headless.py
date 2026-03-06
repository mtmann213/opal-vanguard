#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - USRP Headless Transceiver

import os
import sys
import numpy as np
from gnuradio import gr, blocks, analog, digital, filter, uhd, pdu
import pmt
import yaml
import argparse
import time

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer
from hop_generator_aes import aes_hop_generator
from hop_generator_tod import tod_hop_generator
from session_manager import session_manager

class OpalVanguardUSRPHeadless(gr.top_block):
    def __init__(self, role="ALPHA", serial="", config_path="config.yaml"):
        gr.top_block.__init__(self, f"Opal Vanguard - {role}")
        self.role = role
        print(f"[{self.role}] Loading config from {config_path}...")
        
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
            
        hcfg = self.cfg['hopping']
        hw_cfg = self.cfg['hardware']
        self.samp_rate = hw_cfg['samp_rate']
        self.center_freq = self.cfg['physical']['center_freq']

        # USRP Setup
        args = hw_cfg['args']
        if serial: args += f",serial={serial}"
        
        print(f"[{self.role}] Initializing USRP with args: {args}")
        try:
            self.usrp_sink = uhd.usrp_sink(args, uhd.stream_args(cpu_format="fc32", channels=[0]), "packet_len")
            print(f"[{self.role}] USRP Sink initialized.")
            self.usrp_source = uhd.usrp_source(args, uhd.stream_args(cpu_format="fc32", channels=[0]))
            print(f"[{self.role}] USRP Source initialized.")
            
            for dev in [self.usrp_sink, self.usrp_source]:
                dev.set_samp_rate(self.samp_rate)
                dev.set_center_freq(self.center_freq, 0)
            self.usrp_sink.set_gain(hw_cfg['tx_gain'], 0); self.usrp_sink.set_antenna(hw_cfg['tx_antenna'], 0)
            self.usrp_source.set_gain(hw_cfg['rx_gain'], 0); self.usrp_source.set_antenna(hw_cfg['rx_antenna'], 0)
            print(f"[{self.role}] USRP frequencies and gains set.")
        except Exception as e:
            print(f"FATAL: USRP ERROR: {e}"); sys.exit(1)

        print(f"[{self.role}] Setting up session managers...")
        # Nodes
        self.session_a = session_manager(initial_seed=hcfg['initial_seed'])
        self.session_b = session_manager(initial_seed=hcfg['initial_seed'])
        if hcfg['sync_mode'] == "TOD": self.session_a.state = "CONNECTED"; self.session_b.state = "CONNECTED"
        self.pkt_a = packetizer(config_path=config_path)
        self.depkt_b = depacketizer(config_path=config_path)

        print(f"[{self.role}] Setting up modulation ({self.cfg['physical'].get('modulation', 'GFSK')})...")
        # DSP Chain
        self.pdu_src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len("MISSION DATA"), list("MISSION DATA".encode()))), 3000)
        self.p2s_a = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        mod_type = self.cfg['physical'].get('modulation', 'GFSK')
        sps = self.cfg['physical'].get('samples_per_symbol', 8)
        self.mult_len = blocks.tagged_stream_multiply_length(gr.sizeof_gr_complex*1, "packet_len", sps)
        
        if mod_type == "DBPSK":
            self.mod_a = digital.psk_mod(
                constellation_points=2,
                mod_code=digital.mod_codes.GRAY_CODE,
                differential=True,
                samples_per_symbol=sps,
                excess_bw=0.35,
                verbose=False,
                log=False)
            self.demod_b = digital.psk_demod(
                constellation_points=2,
                differential=True,
                samples_per_symbol=sps,
                excess_bw=0.35,
                phase_bw=6.28/100.0,
                timing_bw=6.28/100.0,
                mod_code=digital.mod_codes.GRAY_CODE,
                verbose=False,
                log=False)
        else:
            # GFSK Default
            freq_dev = self.cfg['physical'].get('freq_dev', 125000)
            mod_sensitivity = (2.0 * np.pi * freq_dev) / self.samp_rate
            self.mod_a = digital.gfsk_mod(samples_per_symbol=sps, sensitivity=mod_sensitivity, bt=0.35, verbose=False, log=False, unpack=False)
            self.demod_b = digital.gfsk_demod(samples_per_symbol=sps, gain_mu=0.1, mu=0.5, omega_relative_limit=0.005, freq_error=0.0)

        print(f"[{self.role}] Initializing hop generator...")
        if hcfg['sync_mode'] == "TOD":
            self.hop_ctrl = tod_hop_generator(key=bytes.fromhex(hcfg['aes_key']), num_channels=hcfg['num_channels'], center_freq=self.center_freq, channel_spacing=hcfg['channel_spacing'], dwell_ms=hcfg['dwell_time_ms'], lookahead_ms=hcfg['lookahead_ms'])
        else:
            self.hop_ctrl = aes_hop_generator(key=bytes.fromhex(hcfg['aes_key']), num_channels=hcfg['num_channels'], center_freq=self.center_freq, channel_spacing=hcfg['channel_spacing'])

        print(f"[{self.role}] Setting up RX filters...")
        # RX Filter
        lpf_taps = filter.firdes.low_pass(1.0, self.samp_rate, 500e3, 100e3)
        self.rx_filter = filter.fir_filter_ccf(1, lpf_taps)

        print(f"[{self.role}] Connecting blocks...")
        # Connections
        self.msg_connect((self.pdu_src, "strobe"), (self.session_a, "data_in"))
        self.msg_connect((self.session_a, "pkt_out"), (self.pkt_a, "in"))
        self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
        self.connect(self.p2s_a, self.mod_a, self.mult_len, self.usrp_sink)
        self.connect(self.usrp_source, self.rx_filter, self.demod_b, self.depkt_b)
        self.msg_connect((self.depkt_b, "out"), (self.session_b, "msg_in"))
        self.msg_connect((self.session_b, "pkt_out"), (self.session_a, "msg_in"))

        print(f"[{self.role}] Setting up hardware handlers and diagnostics...")
        # Hardware Handlers
        class UHDHandler(gr.basic_block):
            def __init__(self, parent):
                gr.basic_block.__init__(self, "UHDHandler", None, None); self.parent = parent
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                try: self.parent.usrp_sink.set_center_freq(pmt.to_double(msg)); self.parent.usrp_source.set_center_freq(pmt.to_double(msg))
                except: pass
        
        self.uhd_h = UHDHandler(self); self.msg_connect((self.hop_ctrl, "freq"), (self.uhd_h, "msg"))

        # Diagnostic Printer
        class DiagPrinter(gr.basic_block):
            def __init__(self, role):
                gr.basic_block.__init__(self, "DiagPrinter", None, None); self.role = role
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                d = {pmt.symbol_to_string(k): (pmt.to_bool(v) if pmt.is_bool(v) else pmt.to_long(v)) for k,v in pmt.dict_to_alist(msg)}
                if d.get('crc_ok'):
                    print(f"[{self.role}] CRC PASS | FEC: {d.get('fec_corrections', 0)}")
        
        self.dp = DiagPrinter(role); self.msg_connect((self.depkt_b, "diagnostics"), (self.dp, "msg"))
        
        # RX Data Printer
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

        # Dwell Timer for Hopping
        self.hcfg = hcfg

    def run_hopping_loop(self):
        print(f"[{self.role}] Starting hopping loop...")
        while True:
            self.hop_ctrl.handle_trigger(pmt.PMT_T)
            time.sleep(self.hcfg['dwell_time_ms'] / 1000.0)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", default="ALPHA", choices=["ALPHA", "BRAVO"])
    parser.add_argument("--serial", default="")
    args = parser.parse_args()
    
    tb = OpalVanguardUSRPHeadless(role=args.role, serial=args.serial)
    tb.start()
    
    print(f"Opal Vanguard Headless Terminal - {args.role} [{args.serial}] Started.")
    
    try:
        # If hopping is enabled, we need to manually trigger it in this headless version
        # since we don't have the Qt timer.
        with open("config.yaml", 'r') as f:
            cfg = yaml.safe_load(f)
        
        if cfg['hopping']['enabled']:
            dwell = cfg['hopping']['dwell_time_ms'] / 1000.0
            while True:
                tb.hop_ctrl.handle_trigger(pmt.PMT_T)
                time.sleep(dwell)
        else:
            # Just keep running
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        tb.stop()
        tb.wait()
        print(f"\nExiting {args.role}.")

if __name__ == '__main__': main()
