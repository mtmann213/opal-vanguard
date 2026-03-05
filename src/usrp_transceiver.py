#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - USRP B210/B205mini Transceiver (Mission Master v3.0)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, analog, digital, qtgui, filter, fft, uhd, pdu
import pmt
import time
import struct
from PyQt5 import Qt
from PyQt5.QtCore import pyqtSignal
import sip
import yaml
import argparse

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer
from hop_generator_aes import aes_hop_generator
from hop_generator_tod import tod_hop_generator
from session_manager import session_manager
from config_validator import validate_config

class OpalVanguardUSRP(gr.top_block, Qt.QWidget):
    status_signal = pyqtSignal(str, str)
    data_signal = pyqtSignal(str)
    diag_signal = pyqtSignal(dict)

    def __init__(self, role="ALPHA", serial="", config_path="mission_configs/level1_soft_link.yaml"):
        gr.top_block.__init__(self, f"Opal Vanguard - {role}")
        Qt.QWidget.__init__(self)
        
        success, msg = validate_config(config_path)
        if not success:
            print(f"FATAL CONFIG ERROR: {msg}"); sys.exit(1)
        
        self.setWindowTitle(f"Opal Vanguard Field Terminal - {role} [{serial}]")
        with open(config_path, 'r') as f: self.cfg = yaml.safe_load(f)
        print(f"--- [OPAL VANGUARD] LAUNCHING {self.cfg['mission']['id']} ---")
            
        hcfg = self.cfg['hopping']
        hw_cfg = self.cfg['hardware']
        self.samp_rate = hw_cfg['samp_rate']
        self.center_freq = self.cfg['physical']['center_freq']

        # UI Layout
        self.main_layout = Qt.QHBoxLayout(); self.setLayout(self.main_layout)
        self.ctrl_panel = Qt.QVBoxLayout(); self.main_layout.addLayout(self.ctrl_panel, 1)
        self.viz_panel = Qt.QVBoxLayout(); self.main_layout.addLayout(self.viz_panel, 3)
        
        self.ctrl_panel.addWidget(Qt.QLabel(f"<b>MISSION ROLE: {role}</b>"))
        self.status_label = Qt.QLabel("Status: CONNECTED")
        self.status_label.setStyleSheet("font-weight: bold; color: green;")
        self.ctrl_panel.addWidget(self.status_label)

        # Health Dashboard
        self.health_box = Qt.QGroupBox("Signal Health Monitor")
        self.health_layout = Qt.QVBoxLayout(); self.health_box.setLayout(self.health_layout)
        
        self.health_layout.addWidget(Qt.QLabel("Signal Confidence:"))
        self.conf_bar = Qt.QProgressBar(); self.conf_bar.setRange(0, 100); self.conf_bar.setValue(0)
        self.health_layout.addWidget(self.conf_bar)
        
        self.crc_led = Qt.QLabel("CRC: ---")
        self.fec_count = Qt.QLabel("FEC Repairs: 0")
        self.blacklist_label = Qt.QLabel("AFH Blacklist: []")
        self.blacklist_label.setStyleSheet("color: darkred; font-weight: bold;")
        
        self.health_layout.addWidget(self.crc_led)
        self.health_layout.addWidget(self.fec_count)
        self.health_layout.addWidget(self.blacklist_label)
        self.ctrl_panel.addWidget(self.health_box)

        # Sliders
        self.tx_gain_slider = Qt.QSlider(Qt.Qt.Horizontal); self.tx_gain_slider.setRange(0, 90); self.tx_gain_slider.setValue(hw_cfg['tx_gain'])
        self.rx_gain_slider = Qt.QSlider(Qt.Qt.Horizontal); self.rx_gain_slider.setRange(0, 90); self.rx_gain_slider.setValue(hw_cfg['rx_gain'])
        self.ctrl_panel.addWidget(Qt.QLabel("TX Gain")); self.ctrl_panel.addWidget(self.tx_gain_slider)
        self.ctrl_panel.addWidget(Qt.QLabel("RX Gain")); self.ctrl_panel.addWidget(self.rx_gain_slider)
        self.tx_gain_slider.valueChanged.connect(self.update_hardware)
        self.rx_gain_slider.valueChanged.connect(self.update_hardware)

        self.text_out = Qt.QTextEdit(); self.text_out.setReadOnly(True); self.ctrl_panel.addWidget(self.text_out)

        # Hardware Setup
        args = hw_cfg['args']
        if serial: args += f",serial={serial}"
        try:
            self.usrp_sink = uhd.usrp_sink(args, uhd.stream_args(cpu_format="fc32", channels=[0]))
            self.usrp_source = uhd.usrp_source(args, uhd.stream_args(cpu_format="fc32", channels=[0]))
            for dev in [self.usrp_sink, self.usrp_source]:
                # GPSDO / 1PPS Support (Tier 4)
                if hw_cfg.get('sync', 'internal') == 'external':
                    dev.set_clock_source("external")
                    dev.set_time_source("external")
                    dev.set_time_unknown_pps(uhd.time_spec())
                elif hw_cfg.get('sync', 'internal') == 'pc_clock':
                    dev.set_time_now(uhd.time_spec(time.time()))
                
                dev.set_samp_rate(self.samp_rate)
                dev.set_center_freq(self.center_freq, 0)
            self.usrp_sink.set_gain(hw_cfg['tx_gain'], 0); self.usrp_sink.set_antenna(hw_cfg['tx_antenna'], 0)
            self.usrp_source.set_gain(hw_cfg['rx_gain'], 0); self.usrp_source.set_antenna(hw_cfg['rx_antenna'], 0)
        except Exception as e: print(f"FATAL: USRP ERROR: {e}"); sys.exit(1)

        # Core Logic
        sid = 1 if role == "ALPHA" else 2
        print(f"--- [PHY] Role: {role} | SID: {sid} | MOD: {self.cfg['physical']['modulation']} ---")
        print(f"--- [LINK] FEC: {self.cfg['link_layer']['use_fec']} | DSSS: {self.cfg['dsss']['enabled']} ---")

        self.session = session_manager(initial_seed=hcfg.get('initial_seed', 0xACE), config_path=config_path)
        self.session.state = "CONNECTED" 
        self.pkt_a = packetizer(config_path=config_path, src_id=sid)
        self.depkt_b = depacketizer(config_path=config_path, src_id=sid, ignore_self=True)

        # DSP Chain
        interval = 1000 if role == "ALPHA" else 1200
        payload_text = f"MISSION DATA FROM {role}"
        self.pdu_src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(payload_text), list(payload_text.encode()))), interval)
        self.p2s_a = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        mod_type = self.cfg['physical'].get('modulation', 'GFSK')
        sps = self.cfg['physical'].get('samples_per_symbol', 8)
        
        if mod_type in ["DBPSK", "DQPSK", "D8PSK"]:
            const_points = 2 if "BPSK" in mod_type else (4 if "QPSK" in mod_type else 8)
            self.mod_a = digital.psk_mod(constellation_points=const_points, mod_code=digital.mod_codes.GRAY_CODE, differential=True, samples_per_symbol=sps, excess_bw=0.35, verbose=False, log=False)
            self.demod_b = digital.psk_demod(constellation_points=const_points, differential=True, samples_per_symbol=sps, excess_bw=0.35, phase_bw=6.28/100.0, timing_bw=6.28/100.0, mod_code=digital.mod_codes.GRAY_CODE, verbose=False, log=False)
        elif mod_type == "MSK":
            self.mod_a = digital.gmsk_mod(samples_per_symbol=sps, bt=0.5)
            self.demod_b = digital.gmsk_demod(samples_per_symbol=sps, gain_mu=0.1, mu=0.5, omega_relative_limit=0.005, freq_error=0.0)
        elif mod_type == "OFDM":
            # Tier 4: Wideband OFDM
            self.mod_a = digital.ofdm_tx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
            self.demod_b = digital.ofdm_rx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
        else:
            freq_dev = self.cfg['physical'].get('freq_dev', 125000)
            mod_sensitivity = (2.0 * np.pi * freq_dev) / self.samp_rate
            self.mod_a = digital.gfsk_mod(samples_per_symbol=sps, sensitivity=mod_sensitivity, bt=0.35)
            self.demod_b = digital.gfsk_demod(samples_per_symbol=sps, gain_mu=0.1, mu=0.5, omega_relative_limit=0.005, freq_error=0.0)

        # Heartbeat
        self.heartbeat = analog.noise_source_c(analog.GR_GAUSSIAN, 0.0001)
        self.add = blocks.add_vcc(1)

        if hcfg.get('sync_mode', 'NONE') == "TOD":
            self.hop_ctrl = tod_hop_generator(key=bytes.fromhex(hcfg.get('aes_key', '00'*32)), num_channels=hcfg.get('num_channels', 50), center_freq=self.center_freq, channel_spacing=hcfg.get('channel_spacing', 150000), dwell_ms=hcfg.get('dwell_time_ms', 200), lookahead_ms=hcfg.get('lookahead_ms', 0))
        else:
            self.hop_ctrl = aes_hop_generator(key=bytes.fromhex(hcfg.get('aes_key', '00'*32)), num_channels=hcfg.get('num_channels', 50), center_freq=self.center_freq, channel_spacing=hcfg.get('channel_spacing', 150000))

        # RX Filter
        lpf_taps = filter.firdes.low_pass(1.0, self.samp_rate, 500e3, 100e3)
        self.rx_filter = filter.fir_filter_ccf(1, lpf_taps)

        # Connections
        self.msg_connect((self.pdu_src, "strobe"), (self.session, "data_in"))
        self.msg_connect((self.session, "pkt_out"), (self.pkt_a, "in"))
        self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
        self.connect(self.p2s_a, self.mod_a, (self.add, 0))
        self.connect(self.heartbeat, (self.add, 1))
        self.connect(self.add, self.usrp_sink)
        self.connect(self.usrp_source, self.rx_filter, self.demod_b, self.depkt_b)
        self.msg_connect((self.depkt_b, "out"), (self.session, "msg_in"))
        self.msg_connect((self.depkt_b, "diagnostics"), (self.session, "crc_fail"))
        self.msg_connect((self.session, "blacklist_out"), (self.hop_ctrl, "blacklist"))

        # Hardware Handler
        class UHDHandler(gr.basic_block):
            def __init__(self, parent):
                gr.basic_block.__init__(self, "UHDHandler", None, None); self.parent = parent
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
                self.message_port_register_in(pmt.intern("blacklist"))
                self.set_msg_handler(pmt.intern("blacklist"), self.handle_bl)
                self.current_bl = []
            def handle_bl(self, msg): self.current_bl = list(pmt.u8vector_elements(msg))
            def handle(self, msg):
                try: 
                    # 1PPS Hardware Triggering (Tier 4)
                    if pmt.is_dict(msg):
                        f = pmt.to_double(pmt.dict_ref(msg, pmt.intern("freq"), pmt.from_double(0)))
                        cmd_time = pmt.to_double(pmt.dict_ref(msg, pmt.intern("time"), pmt.from_double(0)))
                        
                        if cmd_time > 0:
                            time_spec = uhd.time_spec(cmd_time)
                            self.parent.usrp_sink.set_command_time(time_spec)
                            self.parent.usrp_source.set_command_time(time_spec)
                        
                        self.parent.usrp_sink.set_center_freq(f)
                        self.parent.usrp_source.set_center_freq(f)
                        
                        if cmd_time > 0:
                            self.parent.usrp_sink.clear_command_time()
                            self.parent.usrp_source.clear_command_time()
                    else:
                        f = pmt.to_double(msg)
                        self.parent.usrp_sink.set_center_freq(f)
                        self.parent.usrp_source.set_center_freq(f)

                    # Pass current channel to depacketizer diagnostics for health tracking
                    ch = int((f - self.parent.center_freq) / self.parent.cfg['hopping']['channel_spacing'] + (self.parent.cfg['hopping']['num_channels'] // 2))
                    self.parent.depkt_b.current_channel = ch
                except: pass
            def work(self, input_items, output_items): return 0
        
        self.uhd_h = UHDHandler(self)
        if hcfg.get('enabled', True): self.msg_connect((self.hop_ctrl, "freq"), (self.uhd_h, "msg"))
        self.msg_connect((self.session, "blacklist_out"), (self.uhd_h, "blacklist"))

        # GUI Proxy
        class DiagProxy(gr.basic_block):
            def __init__(self, parent):
                gr.basic_block.__init__(self, "DiagProxy", None, None); self.parent = parent
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                try:
                    d = {}
                    if pmt.dict_has_key(msg, pmt.intern("crc_ok")): d["crc_ok"] = pmt.to_bool(pmt.dict_ref(msg, pmt.intern("crc_ok"), pmt.PMT_NIL))
                    if pmt.dict_has_key(msg, pmt.intern("confidence")): d["confidence"] = pmt.to_double(pmt.dict_ref(msg, pmt.intern("confidence"), pmt.PMT_NIL))
                    if pmt.dict_has_key(msg, pmt.intern("fec_repairs")): d["fec_repairs"] = pmt.to_long(pmt.dict_ref(msg, pmt.intern("fec_repairs"), pmt.PMT_NIL))
                    if pmt.dict_has_key(msg, pmt.intern("inverted")): d["inverted"] = pmt.to_bool(pmt.dict_ref(msg, pmt.intern("inverted"), pmt.PMT_NIL))
                    if pmt.dict_has_key(msg, pmt.intern("blacklist")): d["blacklist"] = list(pmt.u8vector_elements(pmt.dict_ref(msg, pmt.intern("blacklist"), pmt.PMT_NIL)))
                    self.parent.diag_signal.emit(d)
                except: pass
            def work(self, input_items, output_items): return 0
        
        self.dp = DiagProxy(self); self.msg_connect((self.depkt_b, "diagnostics"), (self.dp, "msg"))
        self.diag_signal.connect(self.on_diag)
        self.data_signal.connect(lambda p: self.text_out.append(f"<b>[RX]:</b> {p}"))
        
        # Console Logger
        class ConsoleDataLogger(gr.basic_block):
            def __init__(self, parent):
                gr.basic_block.__init__(self, "ConsoleLogger", None, None); self.parent = parent
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                try:
                    p = bytes(pmt.u8vector_elements(pmt.cdr(msg))).decode('utf-8', 'ignore')
                    print(f"\033[94m[DATA RX]: {p}\033[0m")
                    self.parent.data_signal.emit(p)
                except: pass
            def work(self, input_items, output_items): return 0
        self.logger = ConsoleDataLogger(self); self.msg_connect((self.session, "data_out"), (self.logger, "msg"))

        # Viz
        self.snk_waterfall = qtgui.waterfall_sink_c(2048, fft.window.WIN_BLACKMAN_HARRIS, self.center_freq, self.samp_rate, "USRP RF Spectrum", 1)
        self.viz_panel.addWidget(sip.wrapinstance(self.snk_waterfall.qwidget(), Qt.QWidget))
        self.connect(self.usrp_source, self.snk_waterfall)

        self.timer = Qt.QTimer(); self.timer.timeout.connect(lambda: self.hop_ctrl.handle_trigger(pmt.PMT_T))
        if hcfg.get('enabled', True):
            print(f"[Terminal] Hopping ENABLED ({hcfg['dwell_time_ms']}ms)"); self.timer.start(hcfg['dwell_time_ms'])
        else: print("[Terminal] Hopping DISABLED (Fixed Frequency)")

    def update_hardware(self):
        self.usrp_sink.set_gain(self.tx_gain_slider.value(), 0); self.usrp_source.set_gain(self.rx_gain_slider.value(), 0)

    def on_diag(self, d):
        self.crc_led.setText(f"CRC: {'PASS' if d.get('crc_ok') else 'FAIL'}")
        self.crc_led.setStyleSheet(f"color: {'green' if d.get('crc_ok') else 'red'};")
        self.conf_bar.setValue(int(d.get('confidence', 0)))
        self.fec_count.setText(f"FEC Repairs: {d.get('fec_repairs', 0)}")
        if 'blacklist' in d: self.blacklist_label.setText(f"AFH Blacklist: {d['blacklist']}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", default="ALPHA", choices=["ALPHA", "BRAVO"])
    parser.add_argument("--serial", default="")
    parser.add_argument("--config", default="mission_configs/level1_soft_link.yaml")
    args = parser.parse_args()
    qapp = Qt.QApplication(sys.argv)
    tb = OpalVanguardUSRP(role=args.role, serial=args.serial, config_path=args.config)
    tb.start(); tb.show(); qapp.exec_()

if __name__ == '__main__': main()
