#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Signal Diagnostic Viewer (1s Sample-Accurate Capture)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, analog, digital, qtgui, filter, fft, channels, pdu
import pmt
from PyQt5 import Qt
from PyQt5.QtCore import QTimer, pyqtSignal
import sip
import yaml
import time

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from hop_generator_tod import tod_hop_generator

# ----------------------------------------------------------------------
# PRECISION GATE BLOCK
# ----------------------------------------------------------------------
class SampleGate(gr.sync_block):
    def __init__(self, target_samples):
        gr.sync_block.__init__(self, name="SampleGate", in_sig=[np.complex64], out_sig=[np.complex64])
        self.target = target_samples
        self.count = 0
        self.enabled = False
        self.finished_callback = None

    def work(self, input_items, output_items):
        in0 = input_items[0]; out = output_items[0]
        if not self.enabled: return 0
        
        n = min(len(in0), self.target - self.count)
        if n <= 0:
            self.enabled = False
            if self.finished_callback: self.finished_callback()
            return 0
        
        out[:n] = in0[:n]
        self.count += n
        return n

# ----------------------------------------------------------------------
# MAIN VIEWER
# ----------------------------------------------------------------------
class SignalViewer(gr.top_block, Qt.QWidget):
    progress_signal = pyqtSignal(float, float)

    def __init__(self, config_path="config.yaml"):
        gr.top_block.__init__(self, "Opal Vanguard Signal Viewer")
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Opal Vanguard - RF Diagnostic Viewer")
        
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
            
        self.samp_rate = 10000000
        self.center_freq = self.cfg['physical']['center_freq']
        hcfg = self.cfg['hopping']

        self.layout = Qt.QVBoxLayout(); self.setLayout(self.layout)
        
        self.record_btn = Qt.QPushButton("CAPTURE EXACTLY 1s SIGNAL (Sim-Time)")
        self.record_btn.setStyleSheet("height: 50px; font-weight: bold; background-color: #2c3e50; color: white;")
        self.record_btn.clicked.connect(self.start_capture)
        self.layout.addWidget(self.record_btn)
        
        self.progress_label = Qt.QLabel("Capture Progress: 0%")
        self.layout.addWidget(self.progress_label)

        # ----------------------------------------------------------------------
        # SIGNAL CHAIN
        # ----------------------------------------------------------------------
        self.pkt = packetizer(config_path=config_path)
        self.pdu_src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len("DIAGNOSTIC"), list("DIAGNOSTIC".encode()))), 1000)
        self.p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        # Calculate sensitivity from configured frequency deviation
        freq_dev = self.cfg['physical'].get('freq_dev', 125000)
        sensitivity = (2.0 * np.pi * freq_dev) / self.samp_rate
        self.mod = digital.gfsk_mod(samples_per_symbol=8, sensitivity=sensitivity, bt=0.35)
        
        self.rot = blocks.rotator_cc(0)
        self.hop = tod_hop_generator(key=bytes.fromhex(hcfg['aes_key']), num_channels=hcfg['num_channels'], center_freq=self.center_freq, channel_spacing=hcfg['channel_spacing'], dwell_ms=hcfg['dwell_time_ms'])
        
        # Sample-Accurate Gate (1 second * 10MHz = 10M samples)
        self.gate = SampleGate(10000000)
        self.gate.finished_callback = lambda: self.progress_signal.emit(100.0, 0.0)
        self.file_sink = blocks.file_sink(gr.sizeof_gr_complex, "signal_capture.cf32")

        # ----------------------------------------------------------------------
        # VISUALS
        # ----------------------------------------------------------------------
        self.snk_waterfall = qtgui.waterfall_sink_c(2048, fft.window.WIN_BLACKMAN_HARRIS, 0, self.samp_rate, "Wideband 10MHz", 1)
        self.snk_waterfall.set_update_time(0.10)
        
        # ----------------------------------------------------------------------
        # CONNECTIONS
        # ----------------------------------------------------------------------
        self.msg_connect((self.pdu_src, "strobe"), (self.pkt, "in"))
        self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.mod, self.rot)
        self.connect(self.rot, self.gate, self.file_sink)
        
        # Frequency Control
        class FreqHandler(gr.basic_block):
            def __init__(self, rotator):
                gr.basic_block.__init__(self, "FH", None, None); self.rot = rotator
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                f = pmt.to_double(msg); self.rot.set_phase_inc(2 * np.pi * (f - 915e6) / 10e6)
        
        self.fh = FreqHandler(self.rot); self.msg_connect((self.hop, "freq"), (self.fh, "msg"))

        # Visualization
        self.viz_throttle = blocks.throttle(gr.sizeof_gr_complex, self.samp_rate)
        self.connect(self.rot, self.viz_throttle, self.snk_waterfall)

        # ----------------------------------------------------------------------
        # TIMERS & LOGIC
        # ----------------------------------------------------------------------
        self.timer = QTimer(); self.timer.timeout.connect(lambda: self.hop.handle_trigger(pmt.PMT_T)); self.timer.start(hcfg['dwell_time_ms'])
        self.stats_timer = QTimer(); self.stats_timer.timeout.connect(self.update_stats); self.stats_timer.start(500)
        
        self.progress_signal.connect(self.on_progress)

    def start_capture(self):
        print("[Viewer] Starting Sample-Accurate 1s Capture...")
        self.gate.count = 0
        self.gate.enabled = True
        self.record_btn.setEnabled(False)
        self.record_btn.setText("CAPTURING SAMPLES...")

    def update_stats(self):
        if self.gate.enabled:
            progress = (self.gate.count / self.gate.target) * 100
            self.progress_signal.emit(progress, 0.0)

    def on_progress(self, p, speed):
        self.progress_label.setText(f"Capture Progress: {p:.1f}%")
        if p >= 100.0:
            self.record_btn.setEnabled(True)
            self.record_btn.setText("CAPTURE EXACTLY 1s SIGNAL (Sim-Time)")
            print("[Viewer] Capture Complete.")

def main():
    qapp = Qt.QApplication(sys.argv); tb = SignalViewer(); tb.start(); tb.show(); qapp.exec_()
if __name__ == '__main__': main()
