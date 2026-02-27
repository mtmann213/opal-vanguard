#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - USRP B210/B205mini Transceiver (Field Edition)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, analog, digital, qtgui, filter, fft, uhd, pdu
import pmt
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

class OpalVanguardUSRP(gr.top_block, Qt.QWidget):
    status_signal = pyqtSignal(str, str)
    data_signal = pyqtSignal(str)
    diag_signal = pyqtSignal(dict)

    def __init__(self, role="ALPHA", serial="", config_path="config.yaml"):
        gr.top_block.__init__(self, f"Opal Vanguard - {role}")
        Qt.QWidget.__init__(self)
        self.setWindowTitle(f"Opal Vanguard Field Terminal - {role} [{serial}]")
        
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
            
        hcfg = self.cfg['hopping']
        hw_cfg = self.cfg['hardware']
        self.samp_rate = hw_cfg['samp_rate']
        self.center_freq = self.cfg['physical']['center_freq']

        # UI Layout
        self.main_layout = Qt.QHBoxLayout(); self.setLayout(self.main_layout)
        self.ctrl_panel = Qt.QVBoxLayout(); self.main_layout.addLayout(self.ctrl_panel, 1)
        self.viz_panel = Qt.QVBoxLayout(); self.main_layout.addLayout(self.viz_panel, 3)
        
        # Dashboard
        self.ctrl_panel.addWidget(Qt.QLabel(f"<b>MISSION ROLE: {role}</b>"))
        self.status_label = Qt.QLabel("Status: Initializing...")
        self.status_label.setStyleSheet("font-weight: bold; color: blue;")
        self.ctrl_panel.addWidget(self.status_label)

        # Health Dashboard
        self.health_box = Qt.QGroupBox("Signal Health Monitor")
        self.health_layout = Qt.QVBoxLayout(); self.health_box.setLayout(self.health_layout)
        self.crc_led = Qt.QLabel("CRC: ---")
        self.fec_count = Qt.QLabel("FEC Repairs: 0")
        self.inv_warn = Qt.QLabel("Inversion: ---")
        self.health_layout.addWidget(self.crc_led)
        self.health_layout.addWidget(self.fec_count)
        self.health_layout.addWidget(self.inv_warn)
        self.ctrl_panel.addWidget(self.health_box)

        # Gain Sliders
        self.tx_gain_slider = Qt.QSlider(Qt.Qt.Horizontal); self.tx_gain_slider.setRange(0, 90); self.tx_gain_slider.setValue(hw_cfg['tx_gain'])
        self.rx_gain_slider = Qt.QSlider(Qt.Qt.Horizontal); self.rx_gain_slider.setRange(0, 90); self.rx_gain_slider.setValue(hw_cfg['rx_gain'])
        self.ctrl_panel.addWidget(Qt.QLabel("TX Gain")); self.ctrl_panel.addWidget(self.tx_gain_slider)
        self.ctrl_panel.addWidget(Qt.QLabel("RX Gain")); self.ctrl_panel.addWidget(self.rx_gain_slider)
        self.tx_gain_slider.valueChanged.connect(self.update_hardware)
        self.rx_gain_slider.valueChanged.connect(self.update_hardware)

        self.text_out = Qt.QTextEdit(); self.text_out.setReadOnly(True); self.ctrl_panel.addWidget(self.text_out)

        # USRP Setup
        args = hw_cfg['args']
        if serial: args += f",serial={serial}"
        
        try:
            self.usrp_sink = uhd.usrp_sink(args, uhd.stream_args(cpu_format="fc32", channels=[0]))
            self.usrp_source = uhd.usrp_source(args, uhd.stream_args(cpu_format="fc32", channels=[0]))
            for dev in [self.usrp_sink, self.usrp_source]:
                dev.set_samp_rate(self.samp_rate)
                dev.set_center_freq(self.center_freq, 0)
            self.usrp_sink.set_gain(hw_cfg['tx_gain'], 0); self.usrp_sink.set_antenna(hw_cfg['tx_antenna'], 0)
            self.usrp_source.set_gain(hw_cfg['rx_gain'], 0); self.usrp_source.set_antenna(hw_cfg['rx_antenna'], 0)
        except Exception as e:
            print(f"FATAL: USRP ERROR: {e}"); sys.exit(1)

        # Nodes
        self.session_a = session_manager(initial_seed=hcfg['initial_seed'])
        self.session_b = session_manager(initial_seed=hcfg['initial_seed'])
        if hcfg['sync_mode'] == "TOD": self.session_a.state = "CONNECTED"; self.session_b.state = "CONNECTED"
        self.pkt_a = packetizer(config_path=config_path)
        self.depkt_b = depacketizer(config_path=config_path)

        # DSP Chain
        self.pdu_src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len("MISSION DATA"), list("MISSION DATA".encode()))), 3000)
        self.p2s_a = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        mod_type = self.cfg['physical'].get('modulation', 'GFSK')
        sps = self.cfg['physical'].get('samples_per_symbol', 8)
        
        if mod_type == "DBPSK":
            self.mod_a = digital.psk_mod(
                constellation_points=2,
                mod_code=digital.mod_codes.GRAY,
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
                mod_code=digital.mod_codes.GRAY,
                verbose=False,
                log=False)
        else:
            freq_dev = self.cfg['physical'].get('freq_dev', 125000)
            mod_sensitivity = (2.0 * np.pi * freq_dev) / self.samp_rate
            self.mod_a = digital.gfsk_mod(samples_per_symbol=sps, sensitivity=mod_sensitivity, bt=0.35)
            self.demod_b = digital.gfsk_demod(samples_per_symbol=sps, gain_mu=0.1, mu=0.5, omega_relative_limit=0.005, freq_error=0.0)

        # Connections
        self.msg_connect((self.pdu_src, "strobe"), (self.session_a, "data_in"))
        self.msg_connect((self.session_a, "pkt_out"), (self.pkt_a, "in"))
        self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
        self.connect(self.p2s_a, self.mod_a, self.usrp_sink)
        self.connect(self.usrp_source, self.rx_filter, self.demod_b, self.depkt_b)
        self.msg_connect((self.depkt_b, "out"), (self.session_b, "msg_in"))
        self.msg_connect((self.session_b, "pkt_out"), (self.session_a, "msg_in"))

        # Hardware Handlers
        class UHDHandler(gr.basic_block):
            def __init__(self, parent):
                gr.basic_block.__init__(self, "UHDHandler", None, None); self.parent = parent
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                try: self.parent.usrp_sink.set_center_freq(pmt.to_double(msg)); self.parent.usrp_source.set_center_freq(pmt.to_double(msg))
                except: pass
        
        self.uhd_h = UHDHandler(self); self.msg_connect((self.hop_ctrl, "freq"), (self.uhd_h, "msg"))

        # GUI Proxy
        class DiagProxy(gr.basic_block):
            def __init__(self, parent):
                gr.basic_block.__init__(self, "DiagProxy", None, None); self.parent = parent
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                d = {pmt.symbol_to_string(k): (pmt.to_bool(v) if pmt.is_bool(v) else pmt.to_long(v)) for k,v in pmt.dict_to_alist(msg)}
                self.parent.diag_signal.emit(d)
        
        self.dp = DiagProxy(self); self.msg_connect((self.depkt_b, "diagnostics"), (self.dp, "msg"))
        self.diag_signal.connect(self.on_diag)
        self.data_signal.connect(lambda p: self.text_out.append(f"<b>[RX]:</b> {p}"))

        # Viz
        self.snk_waterfall = qtgui.waterfall_sink_c(2048, fft.window.WIN_BLACKMAN_HARRIS, self.center_freq, self.samp_rate, "USRP RF Spectrum", 1)
        self.viz_panel.addWidget(sip.wrapinstance(self.snk_waterfall.qwidget(), Qt.QWidget))
        self.connect(self.usrp_source, self.snk_waterfall)

        self.timer = Qt.QTimer(); self.timer.timeout.connect(lambda: self.hop_ctrl.handle_trigger(pmt.PMT_T)); self.timer.start(hcfg['dwell_time_ms'])

    def update_hardware(self):
        self.usrp_sink.set_gain(self.tx_gain_slider.value(), 0); self.usrp_source.set_gain(self.rx_gain_slider.value(), 0)

    def on_diag(self, d):
        self.crc_led.setText(f"CRC: {'PASS' if d.get('crc_ok') else 'FAIL'}")
        self.crc_led.setStyleSheet(f"color: {'green' if d.get('crc_ok') else 'red'};")
        self.fec_count.setText(f"FEC Repairs: {d.get('fec_corrections', 0)}")
        self.inv_warn.setText(f"Inversion: {'YES' if d.get('inverted') else 'NO'}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", default="ALPHA", choices=["ALPHA", "BRAVO"])
    parser.add_argument("--serial", default="")
    args = parser.parse_args()
    qapp = Qt.QApplication(sys.argv)
    tb = OpalVanguardUSRP(role=args.role, serial=args.serial)
    tb.start(); tb.show(); qapp.exec_()

if __name__ == '__main__': main()
