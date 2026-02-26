#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Full FHSS Lab (DSSS + NRZI + AES-Hop + Config)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, analog, digital, qtgui, filter, fft, channels
import pmt
from PyQt5 import Qt
from PyQt5.QtCore import pyqtSignal
import sip
import yaml

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer
from hop_controller import lfsr_hop_generator
from hop_generator_aes import aes_hop_generator
from session_manager import session_manager

# ----------------------------------------------------------------------
# INTERNAL HANDLER BLOCKS
# ----------------------------------------------------------------------
class FreqHandlerBlock(gr.basic_block):
    def __init__(self, parent):
        gr.basic_block.__init__(self, name="FreqHandler", in_sig=None, out_sig=None)
        self.parent = parent
        self.message_port_register_in(pmt.intern("msg"))
        self.set_msg_handler(pmt.intern("msg"), self.handle_msg)

    def handle_msg(self, msg):
        try:
            freq = pmt.to_double(msg)
            offset = freq - self.parent.center_freq
            phase_inc = 2 * np.pi * offset / self.parent.samp_rate
            self.parent.rot_tx.set_phase_inc(phase_inc)
            self.parent.rot_rx.set_phase_inc(-phase_inc)
        except: pass

class StatusHandlerBlock(gr.basic_block):
    def __init__(self, parent):
        gr.basic_block.__init__(self, name="StatusHandler", in_sig=None, out_sig=None)
        self.parent = parent
        self.message_port_register_in(pmt.intern("msg"))
        self.set_msg_handler(pmt.intern("msg"), self.handle_msg)
    def handle_msg(self, msg):
        self.parent.status_signal.emit(self.parent.session_a.state, self.parent.session_b.state)

class DataHandlerBlock(gr.basic_block):
    def __init__(self, parent):
        gr.basic_block.__init__(self, name="DataHandler", in_sig=None, out_sig=None)
        self.parent = parent
        self.message_port_register_in(pmt.intern("msg"))
        self.set_msg_handler(pmt.intern("msg"), self.handle_msg)
    def handle_msg(self, msg):
        try:
            payload = bytes(pmt.u8vector_elements(pmt.cdr(msg))).decode('utf-8', 'ignore')
            self.parent.data_signal.emit(payload)
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
        self.setWindowTitle("Opal Vanguard - Advanced FHSS Lab")
        
        # Load Config
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
            
        self.samp_rate = self.cfg['physical']['samp_rate']
        self.center_freq = self.cfg['physical']['center_freq']

        # Layout Setup
        self.main_layout = Qt.QHBoxLayout()
        self.setLayout(self.main_layout)
        
        # Panels
        self.ctrl_panel = Qt.QVBoxLayout()
        self.main_layout.addLayout(self.ctrl_panel, 1)
        self.viz_panel = Qt.QVBoxLayout()
        self.main_layout.addLayout(self.viz_panel, 3)
        
        # Status
        self.status_label = Qt.QLabel("Node A: IDLE | Node B: IDLE")
        self.status_label.setStyleSheet("font-weight: bold; color: orange; font-size: 14px;")
        self.ctrl_panel.addWidget(self.status_label)
        
        # Sliders
        self.ctrl_panel.addWidget(Qt.QLabel("<b>Channel Stress Test</b>"))
        
        self.noise_val = Qt.QLabel("Noise Voltage: 0.00 V")
        self.ctrl_panel.addWidget(self.noise_val)
        self.noise_slider = Qt.QSlider(Qt.Qt.Horizontal)
        self.noise_slider.setRange(0, 100)
        self.noise_slider.valueChanged.connect(self.update_channel)
        self.ctrl_panel.addWidget(self.noise_slider)
        
        self.freq_val = Qt.QLabel("Freq Offset: 0.0 Hz")
        self.ctrl_panel.addWidget(self.freq_val)
        self.freq_slider = Qt.QSlider(Qt.Qt.Horizontal)
        self.freq_slider.setRange(-500, 500)
        self.freq_slider.valueChanged.connect(self.update_channel)
        self.ctrl_panel.addWidget(self.freq_slider)

        self.time_val = Qt.QLabel("Timing Offset: 1.000")
        self.ctrl_panel.addWidget(self.time_val)
        self.time_slider = Qt.QSlider(Qt.Qt.Horizontal)
        self.time_slider.setRange(990, 1010)
        self.time_slider.setValue(1000)
        self.time_slider.valueChanged.connect(self.update_channel)
        self.ctrl_panel.addWidget(self.time_slider)

        self.burst_val = Qt.QLabel("Burst Jammer: OFF")
        self.ctrl_panel.addWidget(self.burst_val)
        self.burst_slider = Qt.QSlider(Qt.Qt.Horizontal)
        self.burst_slider.setRange(0, 100)
        self.burst_slider.valueChanged.connect(self.update_channel)
        self.ctrl_panel.addWidget(self.burst_slider)

        self.clear_btn = Qt.QPushButton("Clear Mission Log")
        self.clear_btn.clicked.connect(lambda: self.text_out.clear())
        self.ctrl_panel.addWidget(self.clear_btn)

        self.text_out = Qt.QTextEdit()
        self.text_out.setReadOnly(True)
        self.ctrl_panel.addWidget(self.text_out)

        # ----------------------------------------------------------------------
        # NODES SETUP
        # ----------------------------------------------------------------------
        hcfg = self.cfg['hopping']
        self.session_a = session_manager(initial_seed=hcfg['initial_seed'])
        self.pkt_a = packetizer(config_path=config_path)
        self.session_b = session_manager(initial_seed=hcfg['initial_seed'])
        self.depkt_b = depacketizer(config_path=config_path)

        # ----------------------------------------------------------------------
        # TRANSMITTER CHAIN
        # ----------------------------------------------------------------------
        payload = "Opal Vanguard Advanced Mission Data"
        self.pdu_src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(payload), list(payload.encode()))), 1000)
        self.p2s_a = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        mod_sensitivity = (np.pi * 1.0) / 8.0
        self.mod_a = digital.gfsk_mod(samples_per_symbol=8, sensitivity=mod_sensitivity, bt=0.35)
        self.rot_tx = blocks.rotator_cc(0)
        
        # Hop Controller
        if hcfg['type'] == "AES":
            self.hop_ctrl = aes_hop_generator(
                key=bytes.fromhex(hcfg['key']),
                num_channels=hcfg['num_channels'],
                center_freq=self.center_freq,
                channel_spacing=hcfg['channel_spacing']
            )
        else:
            self.hop_ctrl = lfsr_hop_generator(
                seed=hcfg['initial_seed'],
                num_channels=hcfg['num_channels'],
                center_freq=self.center_freq,
                channel_spacing=hcfg['channel_spacing']
            )
        
        # ----------------------------------------------------------------------
        # CHANNEL & RECEIVER
        # ----------------------------------------------------------------------
        self.channel = channels.channel_model(noise_voltage=0.0, frequency_offset=0.0, epsilon=1.0, taps=[1.0+0j])
        self.rot_rx = blocks.rotator_cc(0)
        self.demod_b = digital.gfsk_demod(samples_per_symbol=8, gain_mu=0.1, mu=0.5, omega_relative_limit=0.005, freq_error=0.0)

        # ----------------------------------------------------------------------
        # HANDLERS & SIGNALS
        # ----------------------------------------------------------------------
        self.freq_handler = FreqHandlerBlock(self)
        self.status_handler = StatusHandlerBlock(self)
        self.data_handler = DataHandlerBlock(self)
        self.status_signal.connect(self.on_status_change)
        self.data_signal.connect(self.on_data_received)

        # ----------------------------------------------------------------------
        # VISUAL SINKS
        # ----------------------------------------------------------------------
        self.snk_waterfall = qtgui.waterfall_sink_c(2048, fft.window.WIN_BLACKMAN_HARRIS, 0, self.samp_rate, "Wideband Spectrum", 1)
        self.snk_rx_freq = qtgui.freq_sink_c(2048, fft.window.WIN_BLACKMAN_HARRIS, 0, self.samp_rate, "De-hopped Baseband", 1)
        self.viz_panel.addWidget(sip.wrapinstance(self.snk_waterfall.qwidget(), Qt.QWidget))
        self.viz_panel.addWidget(sip.wrapinstance(self.snk_rx_freq.qwidget(), Qt.QWidget))

        # ----------------------------------------------------------------------
        # CONNECTIONS
        # ----------------------------------------------------------------------
        self.msg_connect((self.pdu_src, "strobe"), (self.session_a, "data_in"))
        self.msg_connect((self.session_a, "pkt_out"), (self.pkt_a, "in"))
        self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
        self.connect(self.p2s_a, self.mod_a, self.rot_tx, self.channel)
        
        self.connect(self.channel, self.rot_rx, self.demod_b, self.depkt_b)
        self.msg_connect((self.depkt_b, "out"), (self.session_b, "msg_in"))
        self.msg_connect((self.session_b, "pkt_out"), (self.session_a, "msg_in"))

        self.msg_connect((self.hop_ctrl, "freq"), (self.freq_handler, "msg"))
        self.msg_connect((self.session_a, "pkt_out"), (self.status_handler, "msg"))
        self.msg_connect((self.session_b, "pkt_out"), (self.status_handler, "msg"))
        self.msg_connect((self.session_b, "data_out"), (self.data_handler, "msg"))

        # Viz Throttle
        self.viz_throttle = blocks.throttle(gr.sizeof_gr_complex, self.samp_rate)
        self.connect(self.channel, self.viz_throttle)
        self.connect(self.viz_throttle, self.snk_waterfall)
        self.connect(self.rot_rx, self.snk_rx_freq)

        self.timer = Qt.QTimer()
        self.timer.timeout.connect(lambda: self.hop_ctrl.handle_trigger(pmt.PMT_T))
        self.timer.start(hcfg['dwell_time_ms'])

    def update_channel(self):
        noise = self.noise_slider.value() / 100.0
        freq_off_rel = self.freq_slider.value() / 10000.0
        epsilon = self.time_slider.value() / 1000.0
        burst = self.burst_slider.value()
        self.noise_val.setText(f"Noise Voltage: {noise:.2f} V")
        self.freq_val.setText(f"Freq Offset: {freq_off_rel*self.samp_rate/1e3:.1f} kHz")
        self.time_val.setText(f"Timing Offset: {epsilon:.3f}")
        self.burst_val.setText(f"Burst Jammer: {burst}% Intensity")
        self.channel.set_noise_voltage(noise + (burst/100.0 * 0.5))
        self.channel.set_frequency_offset(freq_off_rel)
        self.channel.set_timing_offset(epsilon)

    def on_status_change(self, state_a, state_b):
        self.status_label.setText(f"Node A: {state_a} | Node B: {state_b}")
        if state_a == "CONNECTED" and state_b == "CONNECTED":
            self.status_label.setStyleSheet("font-weight: bold; color: green; font-size: 14px;")
        else:
            self.status_label.setStyleSheet("font-weight: bold; color: orange; font-size: 14px;")

    def on_data_received(self, payload):
        self.text_out.append(f"<b>[RX]:</b> {payload}")

def main():
    qapp = Qt.QApplication(sys.argv)
    tb = OpalVanguardVisualDemo()
    tb.start()
    tb.show()
    def quitting():
        tb.stop()
        tb.wait()
    qapp.aboutToQuit.connect(quitting)
    qapp.exec_()

if __name__ == '__main__':
    main()
