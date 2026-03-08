#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - USRP B210/B205mini Transceiver (Tactical OFDM Build v10.18)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, analog, digital, qtgui, filter, fft, uhd, pdu
import pmt
import time
import struct
import socket
import threading
import base64
import json
from PyQt5 import Qt
from PyQt5.QtCore import pyqtSignal, QTimer
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

# ----------------------------------------------------------------------
# LOGGING REDIRECTION
# ----------------------------------------------------------------------
class LoggerProxy:
    def __init__(self, original, log_file):
        self.original = original; self.log_file = log_file
    def write(self, data):
        self.original.write(data); self.log_file.write(data)
    def flush(self):
        self.original.flush(); self.log_file.flush()

class OpalVanguardUSRP(gr.top_block, Qt.QWidget):
    status_signal = pyqtSignal(str, str)
    data_signal = pyqtSignal(str)
    diag_signal = pyqtSignal(dict)
    reboot_signal = pyqtSignal(str)
    ghost_trigger_signal = pyqtSignal()

    def __init__(self, role="ALPHA", serial="", config_path="mission_configs/level1_soft_link.yaml"):
        # Role-based Mission Observer
        self.log_filename = f"mission_{role}.log"
        self.log_f = open(self.log_filename, "a", buffering=1)
        sys.stdout = LoggerProxy(sys.stdout, self.log_f)
        sys.stderr = LoggerProxy(sys.stderr, self.log_f)
        print(f"\n--- [{role} MISSION OBSERVER START: {time.ctime()}] ---")

        gr.top_block.__init__(self, f"Opal Vanguard - {role}")
        Qt.QWidget.__init__(self)
        
        self.role = role; self.serial = serial; self.config_path = config_path
        with open(config_path, 'r') as f: self.cfg = yaml.safe_load(f)
        print(f"--- [OPAL VANGUARD] {self.cfg['mission']['id']} ONLINE ---")
        
        h_cfg = self.cfg.get('hopping', {})
        hw_cfg = self.cfg.get('hardware', {})
        self.samp_rate = hw_cfg.get('samp_rate', 2000000)
        self.center_freq = self.cfg['physical'].get('center_freq', 915000000)
        self.payload_type = self.cfg.get('application_layer', {}).get('payload_type', 'heartbeat')

        # UI Setup
        self.layout = Qt.QVBoxLayout(); self.setLayout(self.layout)
        self.info_label = Qt.QLabel(f"<b>ROLE: {role} | SERIAL: {serial}</b>"); self.layout.addWidget(self.info_label)
        self.status_label = Qt.QLabel("Status: IDLE"); self.status_label.setStyleSheet("color: gray; font-weight: bold;"); self.layout.addWidget(self.status_label)
        self.status_signal.connect(lambda s, c: (self.status_label.setText(f"Status: {s}"), self.status_label.setStyleSheet(f"color: {c}; font-weight: bold;")))

        self.tabs = Qt.QTabWidget(); self.layout.addWidget(self.tabs)
        self.ctrl_tab = Qt.QWidget(); self.tabs.addTab(self.ctrl_tab, "Control")
        self.ctrl_layout = Qt.QVBoxLayout(self.ctrl_tab)
        
        self.health_group = Qt.QGroupBox("Signal Health Monitor"); self.ctrl_layout.addWidget(self.health_group)
        self.health_layout = Qt.QVBoxLayout(self.health_group)
        self.conf_bar = Qt.QProgressBar(); self.conf_bar.setRange(0, 100); self.health_layout.addWidget(Qt.QLabel("Confidence:")); self.health_layout.addWidget(self.conf_bar)
        self.crc_led = Qt.QLabel("CRC: ---"); self.fec_count = Qt.QLabel("FEC Repairs: 0"); self.blacklist_label = Qt.QLabel("AFH Blacklist: [DISABLED]"); self.blacklist_label.setStyleSheet("color: gray; font-weight: bold;")
        self.health_layout.addWidget(self.crc_led); self.health_layout.addWidget(self.fec_count); self.health_layout.addWidget(self.blacklist_label)

        self.tx_gain_slider = Qt.QSlider(Qt.Qt.Horizontal); self.tx_gain_slider.setRange(0, 90); self.tx_gain_slider.setValue(hw_cfg.get('tx_gain', 70))
        self.rx_gain_slider = Qt.QSlider(Qt.Qt.Horizontal); self.rx_gain_slider.setRange(0, 90); self.rx_gain_slider.setValue(hw_cfg.get('rx_gain', 70))
        self.ctrl_layout.addWidget(Qt.QLabel("TX Gain")); self.ctrl_layout.addWidget(self.tx_gain_slider)
        self.ctrl_layout.addWidget(Qt.QLabel("RX Gain")); self.ctrl_layout.addWidget(self.rx_gain_slider)
        self.tx_gain_slider.valueChanged.connect(lambda v: self.usrp_sink.set_gain(v, 0)); self.rx_gain_slider.valueChanged.connect(lambda v: self.usrp_source.set_gain(v, 0))

        self.text_out = Qt.QTextEdit(); self.text_out.setReadOnly(True); self.ctrl_layout.addWidget(self.text_out)
        
        # Data Source Initialization
        if self.payload_type == 'heartbeat':
            interval = 1000 if role == "ALPHA" else 1200
            self.pdu_src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(f"HEARTBEAT FROM {role}"), list(f"HEARTBEAT FROM {role}".encode()))), interval)
        elif self.payload_type == 'chat':
            self.pdu_src = blocks.message_debug()
            self.chat_layout = Qt.QHBoxLayout(); self.chat_input = Qt.QLineEdit(); self.chat_btn = Qt.QPushButton("Send")
            self.chat_layout.addWidget(self.chat_input); self.chat_layout.addWidget(self.chat_btn); self.ctrl_layout.addLayout(self.chat_layout)
            self.chat_btn.clicked.connect(self.send_chat)
        else:
            self.pdu_src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(f"HEARTBEAT FROM {role}"), list(f"HEARTBEAT FROM {role}".encode()))), 1000)
        
        self.viz_tab = Qt.QWidget(); self.tabs.addTab(self.viz_tab, "Visualization")
        self.viz_layout = Qt.QVBoxLayout(self.viz_tab); self.viz_panel = Qt.QVBoxLayout(); self.viz_layout.addLayout(self.viz_panel)

        # Hardware
        args_str = hw_cfg['args']
        if serial: args_str += f",serial={serial}"
        try:
            self.usrp_sink = uhd.usrp_sink(args_str, uhd.stream_args(cpu_format="fc32", channels=[0]), "packet_len")
            self.usrp_source = uhd.usrp_source(args_str, uhd.stream_args(cpu_format="fc32", channels=[0]))
            for dev in [self.usrp_sink, self.usrp_source]:
                dev.set_samp_rate(self.samp_rate); dev.set_center_freq(self.center_freq, 0)
            self.usrp_sink.set_gain(hw_cfg['tx_gain'], 0); self.usrp_sink.set_antenna(hw_cfg['tx_antenna'], 0)
            self.usrp_source.set_gain(hw_cfg['rx_gain'], 0); self.usrp_source.set_antenna(hw_cfg['rx_antenna'], 0)
            self.usrp_sink.set_time_now(uhd.time_spec(time.time()))
            print(f"[TERMINAL] USRP Clock Synced to: {time.ctime()}")
        except Exception as e: print(f"FATAL USRP: {e}"); sys.exit(1)

        sid = 1 if role == "ALPHA" else 2
        self.session = session_manager(initial_seed=h_cfg.get('initial_seed', 0xACE), config_path=config_path)
        self.pkt_a = packetizer(config_path=config_path, src_id=sid); self.depkt_b = depacketizer(config_path=config_path, src_id=sid, ignore_self=True)
        
        if self.cfg['link_layer'].get('use_comsec', False):
            key = bytes.fromhex(self.cfg['link_layer'].get('comsec_key', '00'*32))
            self.pkt_a.use_comsec = True; self.pkt_a.comsec_key = key
            self.depkt_b.use_comsec = True; self.depkt_b.comsec_key = key
            print("[TERMINAL] COMSEC (AES-CTR) ENABLED")

        self.p2s_a = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        mod_type = self.cfg['physical'].get('modulation', 'GFSK'); sps = self.cfg['physical'].get('samples_per_symbol', 10)
        self.mult_len = blocks.tagged_stream_multiply_length(gr.sizeof_gr_complex*1, "packet_len", sps)
        
        if mod_type == "GFSK":
            sens = (2.0 * np.pi * self.cfg['physical'].get('freq_dev', 25000)) / self.samp_rate
            self.mod_a = digital.gfsk_mod(sps, sens, 0.35, False, False, False)
            self.demod_b = digital.gfsk_demod(sps, sens, 0.4, 0.5, 0.01, 0.0)
        elif mod_type == "OFDM":
            # Simplified OFDM Pipeline for Stability
            # 64 carriers, 16 CP, BPSK mapping
            self.mod_a = digital.ofdm_tx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
            self.demod_b = digital.ofdm_rx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
            # Convert OFDM bytes back to bits for our depacketizer
            self.unpack = blocks.packed_to_unpacked_bb(1, gr.GR_MSB_FIRST)
        else:
            self.mod_a = digital.gfsk_mod(sps, (2.0*np.pi*25000)/self.samp_rate, 0.35, False, False, False)
            self.demod_b = digital.gfsk_demod(sps, (2.0*np.pi*25000)/self.samp_rate, 0.1, 0.5, 0.005, 0.0)

        self.rx_filter = filter.fir_filter_ccf(1, filter.firdes.low_pass(1.0, self.samp_rate, 100e3, 50e3))

        if h_cfg.get('sync_mode') == "TOD":
            self.hop_ctrl = tod_hop_generator(key=bytes.fromhex(h_cfg.get('aes_key', '00'*32)), num_channels=h_cfg.get('num_channels', 50), center_freq=self.center_freq, channel_spacing=h_cfg.get('channel_spacing', 150000), dwell_ms=h_cfg.get('dwell_time_ms', 200), lookahead_ms=h_cfg.get('lookahead_ms', 0))
        else:
            self.hop_ctrl = aes_hop_generator(key=bytes.fromhex(h_cfg.get('aes_key', '00'*32)), num_channels=h_cfg.get('num_channels', 50), center_freq=self.center_freq, channel_spacing=h_cfg.get('channel_spacing', 150000))

        # Handlers
        class UIHandler(gr.basic_block):
            def __init__(self, parent): gr.basic_block.__init__(self, "UIHandler", None, None); self.p = parent; self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                try: self.p.data_signal.emit(bytes(pmt.u8vector_elements(pmt.cdr(msg))).decode('utf-8', errors='replace'))
                except: pass
            def work(self, i, o): return 0
        self.ui_h = UIHandler(self); self.data_signal.connect(lambda m: self.text_out.append(f"<b>[DATA RX]:</b> {m}"))

        class StatusHandler(gr.basic_block):
            def __init__(self, parent): gr.basic_block.__init__(self, "StatusHandler", None, None); self.p = parent; self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                try:
                    s = pmt.to_python(pmt.dict_ref(msg, pmt.intern("state"), pmt.from_long(0)))
                    self.p.status_signal.emit(s, "green" if s == "CONNECTED" else "orange")
                except: pass
            def work(self, i, o): return 0
        self.status_h = StatusHandler(self)

        class DiagHandler(gr.basic_block):
            def __init__(self, parent): gr.basic_block.__init__(self, "DiagHandler", None, None); self.p = parent; self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                try: d = {"confidence": pmt.to_double(pmt.dict_ref(msg, pmt.intern("confidence"), pmt.from_double(0))), "crc_ok": pmt.to_bool(pmt.dict_ref(msg, pmt.intern("crc_ok"), pmt.from_bool(False))), "fec_repairs": pmt.to_long(pmt.dict_ref(msg, pmt.intern("fec_repairs"), pmt.from_long(0)))}
                except: pass
            def work(self, i, o): return 0
        self.diag_h = DiagHandler(self); self.diag_signal.connect(self.on_diag)

        # Connect
        src_port = "out" if self.payload_type in ['chat', 'file'] else "strobe"
        self.msg_connect((self.pdu_src, src_port), (self.session, "data_in"))
        self.msg_connect((self.session, "pkt_out"), (self.pkt_a, "in"))
        self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
        
        if mod_type == "OFDM":
            # Direct Byte Routing for OFDM
            self.connect(self.p2s_a, self.mod_a, self.usrp_sink)
            self.connect(self.usrp_source, self.rx_filter, self.demod_b, self.unpack, self.depkt_b)
        else:
            self.connect(self.p2s_a, self.mod_a, self.mult_len, self.usrp_sink)
            self.connect(self.usrp_source, self.rx_filter, self.demod_b, self.depkt_b)

        self.msg_connect((self.depkt_b, "out"), (self.session, "msg_in"))
        self.msg_connect((self.depkt_b, "diagnostics"), (self.diag_h, "msg"))
        self.msg_connect((self.session, "status_out"), (self.status_h, "msg"))
        self.msg_connect((self.session, "data_out"), (self.ui_h, "msg"))

        # GUI Sinks
        self.snk_waterfall = qtgui.waterfall_sink_c(2048, fft.window.WIN_BLACKMAN_HARRIS, self.center_freq, self.samp_rate, "Spectrum", 1)
        self.snk_freq = qtgui.freq_sink_c(1024, fft.window.WIN_BLACKMAN_HARRIS, self.center_freq, self.samp_rate, "Baseband Spectrum", 1)
        self.snk_scope = qtgui.time_sink_f(4096, self.samp_rate, "Signal Scope (Bits)", 1)
        self.snk_scope.set_trigger_mode(qtgui.TRIG_MODE_TAG, qtgui.TRIG_SLOPE_POS, 0.5, 0.0, 0, "rx_sync")
        self.rx_b2f = blocks.uchar_to_float()
        
        self.viz_panel.addWidget(sip.wrapinstance(self.snk_waterfall.qwidget(), Qt.QWidget))
        self.viz_panel.addWidget(sip.wrapinstance(self.snk_freq.qwidget(), Qt.QWidget))
        self.viz_panel.addWidget(sip.wrapinstance(self.snk_scope.qwidget(), Qt.QWidget))
        
        self.connect(self.usrp_source, self.snk_waterfall)
        self.connect(self.rx_filter, self.snk_freq)
        self.connect(self.depkt_b, self.rx_b2f, self.snk_scope)

        self.timer = QTimer(); self.timer.timeout.connect(lambda: self.hop_ctrl.handle_trigger(pmt.PMT_T))
        if h_cfg.get('enabled', True): self.timer.start(h_cfg['dwell_time_ms'])
        self.reboot_signal.connect(self.execute_cold_reboot)

    def on_diag(self, d):
        self.conf_bar.setValue(int(d['confidence'])); self.crc_led.setText(f"CRC: {'OK' if d['crc_ok'] else 'FAIL'}")
        self.crc_led.setStyleSheet(f"color: {'green' if d['crc_ok'] else 'red'}; font-weight: bold;")
        self.fec_count.setText(f"FEC Repairs: {d['fec_repairs']}")

    def execute_cold_reboot(self, target):
        self.stop(); self.wait(); time.sleep(1); python = sys.executable; os.execv(python, [python, sys.argv[0], "--role", self.role, "--serial", self.serial, "--config", target])

    @Qt.pyqtSlot(float)
    def set_usrp_freq(self, f):
        try: self.usrp_sink.set_center_freq(f); self.usrp_source.set_center_freq(f)
        except: pass

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--role", choices=["ALPHA", "BRAVO"], default="ALPHA"); parser.add_argument("--serial", default=""); parser.add_argument("--config", default="mission_configs/level1_soft_link.yaml")
    args = parser.parse_args(); qapp = Qt.QApplication(sys.argv); tb = OpalVanguardUSRP(args.role, args.serial, args.config); tb.start(); tb.show(); qapp.exec_()

if __name__ == '__main__': main()
