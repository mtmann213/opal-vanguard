#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Full FHSS Lab (Multi-Modulation Support)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, analog, digital, qtgui, filter, fft, channels, pdu
import pmt
from PyQt5 import Qt
from PyQt5.QtCore import pyqtSignal, QTimer
import sip
import yaml
import time

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer
from hop_controller import lfsr_hop_generator
from hop_generator_aes import aes_hop_generator
from hop_generator_tod import tod_hop_generator
from session_manager import session_manager

# ----------------------------------------------------------------------
# INTERNAL HANDLER BLOCKS
# ----------------------------------------------------------------------
class FreqHandlerBlock(gr.basic_block):
    def __init__(self, parent):
        gr.basic_block.__init__(self, name="FreqHandler", in_sig=None, out_sig=None)
        self.parent = parent
        self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle_msg)
    def handle_msg(self, msg):
        try:
            freq = pmt.to_double(msg); offset = freq - self.parent.center_freq
            phase_inc = 2 * np.pi * offset / self.parent.samp_rate
            self.parent.rot_tx.set_phase_inc(phase_inc); self.parent.rot_rx.set_phase_inc(-phase_inc)
        except: pass

class StatusHandlerBlock(gr.basic_block):
    def __init__(self, parent):
        gr.basic_block.__init__(self, name="StatusHandler", in_sig=None, out_sig=None)
        self.parent = parent
        self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle_msg)
    def handle_msg(self, msg): self.parent.status_signal.emit(self.parent.session_a.state, self.parent.session_b.state)

class DataHandlerBlock(gr.basic_block):
    def __init__(self, parent):
        gr.basic_block.__init__(self, name="DataHandler", in_sig=None, out_sig=None)
        self.parent = parent
        self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle_msg)
    def handle_msg(self, msg):
        try:
            p = bytes(pmt.u8vector_elements(pmt.cdr(msg))).decode('utf-8', 'ignore'); self.parent.data_signal.emit(p)
        except: pass

# ----------------------------------------------------------------------
# MAIN GUI CLASS
# ----------------------------------------------------------------------
class OpalVanguardVisualDemo(gr.top_block, Qt.QWidget):
    status_signal = pyqtSignal(str, str)
    data_signal = pyqtSignal(str)

    def __init__(self, config_path="config.yaml"):
        gr.top_block.__init__(self, "Opal Vanguard Lab")
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Opal Vanguard - Wideband 10MHz Lab")
        
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
            
        self.samp_rate = self.cfg['physical']['samp_rate']
        self.center_freq = self.cfg['physical']['center_freq']
        hcfg = self.cfg['hopping']
        mod_type = self.cfg['physical'].get('modulation', 'GFSK')

        # Layout
        self.main_layout = Qt.QHBoxLayout(); self.setLayout(self.main_layout)
        self.ctrl_panel = Qt.QVBoxLayout(); self.main_layout.addLayout(self.ctrl_panel, 1)
        self.viz_panel = Qt.QVBoxLayout(); self.main_layout.addLayout(self.viz_panel, 3)
        
        # Dashboard
        self.status_label = Qt.QLabel("Initial Syncing...")
        self.status_label.setStyleSheet("font-weight: bold; color: orange; font-size: 14px;")
        self.ctrl_panel.addWidget(self.status_label)
        
        mode_info = f"MOD: {mod_type} | SYNC: {hcfg['sync_mode']}"
        self.ctrl_panel.addWidget(Qt.QLabel(f"<font color='blue'>{mode_info}</font>"))

        self.record_btn = Qt.QPushButton("START 1s IQ CAPTURE")
        self.record_btn.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        self.record_btn.clicked.connect(self.start_capture)
        self.ctrl_panel.addWidget(self.record_btn)

        # Stress Sliders
        self.ctrl_panel.addWidget(Qt.QLabel("<b>Channel Stress</b>"))
        self.noise_val = Qt.QLabel("Noise: 0.00 V"); self.ctrl_panel.addWidget(self.noise_val)
        self.noise_slider = Qt.QSlider(Qt.Qt.Horizontal); self.noise_slider.setRange(0, 100); self.noise_slider.valueChanged.connect(self.update_channel); self.ctrl_panel.addWidget(self.noise_slider)
        self.burst_slider = Qt.QSlider(Qt.Qt.Horizontal); self.burst_slider.setRange(0, 100); self.burst_slider.valueChanged.connect(self.update_channel); self.ctrl_panel.addWidget(Qt.QLabel("Burst Jammer")); self.ctrl_panel.addWidget(self.burst_slider)

        self.clear_btn = Qt.QPushButton("Clear Mission Log")
        self.clear_btn.clicked.connect(lambda: self.text_out.clear()); self.ctrl_panel.addWidget(self.clear_btn)
        self.text_out = Qt.QTextEdit(); self.text_out.setReadOnly(True); self.ctrl_panel.addWidget(self.text_out)

        # ----------------------------------------------------------------------
        # BLOCKS
        # ----------------------------------------------------------------------
        self.session_a = session_manager(initial_seed=hcfg['initial_seed'])
        self.session_b = session_manager(initial_seed=hcfg['initial_seed'])
        if hcfg['sync_mode'] == "TOD": self.session_a.state = "CONNECTED"; self.session_b.state = "CONNECTED"
            
        self.pkt_a = packetizer(config_path=config_path)
        self.depkt_b = depacketizer(config_path=config_path)

        self.pdu_src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len("MISSION DATA"), list("MISSION DATA".encode()))), 3000)
        self.p2s_a = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        # --- Modulation Switching ---
        sps = self.cfg['physical'].get('samples_per_symbol', 8)
        if mod_type == "DBPSK":
            self.mod_a = digital.dbpsk_mod(samples_per_symbol=sps, excess_bw=0.35)
            self.demod_b = digital.dbpsk_demod(samples_per_symbol=sps, excess_bw=0.35)
        else: # GFSK Default
            freq_dev = self.cfg['physical'].get('freq_dev', 125000)
            sensitivity = (2.0 * np.pi * freq_dev) / self.samp_rate
            self.mod_a = digital.gfsk_mod(samples_per_symbol=sps, sensitivity=sensitivity, bt=0.35)
            self.demod_b = digital.gfsk_demod(samples_per_symbol=sps, gain_mu=0.1, mu=0.5, omega_relative_limit=0.005, freq_error=0.0)

        self.rot_tx = blocks.rotator_cc(0)
        
        # Hop Controller
        if hcfg['sync_mode'] == "TOD":
            self.hop_ctrl = tod_hop_generator(key=bytes.fromhex(hcfg['aes_key']), num_channels=hcfg['num_channels'], center_freq=self.center_freq, channel_spacing=hcfg['channel_spacing'], dwell_ms=hcfg['dwell_time_ms'], lookahead_ms=hcfg['lookahead_ms'])
        else:
            self.hop_ctrl = aes_hop_generator(key=bytes.fromhex(hcfg['aes_key']), num_channels=hcfg['num_channels'], center_freq=self.center_freq, channel_spacing=hcfg['channel_spacing'])
        
        self.channel = channels.channel_model(noise_voltage=0.0, frequency_offset=0.0, epsilon=1.0, taps=[1.0+0j])
        self.rot_rx = blocks.rotator_cc(0)
        
        cutoff = min(0.8e6, self.samp_rate / 2.1)
        lpf_taps = filter.firdes.low_pass(1.0, self.samp_rate, cutoff, 100e3)
        self.rx_filter = filter.fir_filter_ccf(1, lpf_taps)
        
        self.stabilizer = blocks.delay(gr.sizeof_gr_complex, 100)

        # IQ Recorder Sink
        self.file_sink = blocks.file_sink(gr.sizeof_gr_complex, "mission_capture_10M.cf32")
        self.valve = blocks.copy(gr.sizeof_gr_complex); self.valve.set_enabled(False)

        # ----------------------------------------------------------------------
        # VISUAL SINKS
        # ----------------------------------------------------------------------
        self.snk_waterfall = qtgui.waterfall_sink_c(2048, fft.window.WIN_BLACKMAN_HARRIS, 0, self.samp_rate, "Wideband Spectrum", 1)
        self.snk_waterfall.set_update_time(0.15)
        self.snk_rx_freq = qtgui.freq_sink_c(1024, fft.window.WIN_BLACKMAN_HARRIS, 0, self.samp_rate, "De-hopped Baseband", 1)
        self.viz_panel.addWidget(sip.wrapinstance(self.snk_waterfall.qwidget(), Qt.QWidget))
        self.viz_panel.addWidget(sip.wrapinstance(self.snk_rx_freq.qwidget(), Qt.QWidget))

        # ----------------------------------------------------------------------
        # CONNECTIONS
        # ----------------------------------------------------------------------
        self.msg_connect((self.pdu_src, "strobe"), (self.session_a, "data_in"))
        self.msg_connect((self.session_a, "pkt_out"), (self.pkt_a, "in"))
        self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
        self.connect(self.p2s_a, self.mod_a, self.rot_tx, self.channel)
        self.connect(self.channel, self.rot_rx, self.rx_filter, self.stabilizer, self.demod_b, self.depkt_b)
        self.msg_connect((self.depkt_b, "out"), (self.session_b, "msg_in"))
        self.msg_connect((self.session_b, "pkt_out"), (self.session_a, "msg_in"))

        self.freq_h = FreqHandlerBlock(self); self.msg_connect((self.hop_ctrl, "freq"), (self.freq_h, "msg"))
        self.stat_h = StatusHandlerBlock(self); self.msg_connect((self.session_a, "pkt_out"), (self.stat_h, "msg"))
        self.data_h = DataHandlerBlock(self); self.msg_connect((self.session_b, "data_out"), (self.data_h, "msg"))

        self.connect(self.channel, self.valve, self.file_sink)
        self.viz_throttle = blocks.throttle(gr.sizeof_gr_complex, self.samp_rate)
        self.connect(self.channel, self.viz_throttle, self.snk_waterfall)
        self.connect(self.rot_rx, self.snk_rx_freq)

        self.timer = Qt.QTimer(); self.timer.timeout.connect(lambda: self.hop_ctrl.handle_trigger(pmt.PMT_T)); self.timer.start(hcfg['dwell_time_ms'])
        self.status_signal.connect(self.on_status_change)
        self.data_signal.connect(lambda p: self.text_out.append(f"<b>[RX]:</b> {p}"))

    def start_capture(self):
        self.valve.set_enabled(True); self.record_btn.setEnabled(False); self.record_btn.setText("RECORDING...")
        QTimer.singleShot(1000, self.stop_capture) # 1s capture

    def stop_capture(self):
        self.valve.set_enabled(False); self.record_btn.setEnabled(True); self.record_btn.setText("START 1s IQ CAPTURE")

    def update_channel(self):
        n = self.noise_slider.value() / 100.0; b = self.burst_slider.value()
        self.noise_val.setText(f"Noise: {n:.2f} V"); self.channel.set_noise_voltage(n + (b/100.0 * 0.5))

    def on_status_change(self, sa, sb):
        self.status_label.setText(f"Node A: {sa} | Node B: {sb}")
        if sa == "CONNECTED": self.status_label.setStyleSheet("color: green; font-weight: bold;")

def main():
    qapp = Qt.QApplication(sys.argv); tb = OpalVanguardVisualDemo(); tb.start(); tb.show(); qapp.exec_()
if __name__ == '__main__': main()
