#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Full Loopback Visual Demo (Thread-Safe & Robust)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, analog, digital, qtgui, filter, fft
import pmt
from PyQt5 import Qt
from PyQt5.QtCore import pyqtSignal
import sip

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer
from hop_controller import lfsr_hop_generator
from session_manager import session_manager

# ----------------------------------------------------------------------
# INTERNAL HANDLER BLOCKS (Fixes AttributeError scoping issues)
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
        except Exception as e:
            print(f"FreqHandler Error: {e}")

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
        except Exception as e:
            print(f"DataHandler Error: {e}")

# ----------------------------------------------------------------------
# MAIN GUI CLASS
# ----------------------------------------------------------------------
class OpalVanguardVisualDemo(gr.top_block, Qt.QWidget):
    status_signal = pyqtSignal(str, str)
    data_signal = pyqtSignal(str)

    def __init__(self, samp_rate=2e6, center_freq=915e6):
        gr.top_block.__init__(self, "Opal Vanguard Full Loopback")
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Opal Vanguard - Full FHSS Handshake Demo")
        
        self.samp_rate = samp_rate
        self.center_freq = center_freq

        # Layout Setup
        self.layout = Qt.QVBoxLayout()
        self.setLayout(self.layout)
        
        # Status Display
        self.status_label = Qt.QLabel("Node A: IDLE | Node B: IDLE")
        self.status_label.setStyleSheet("font-weight: bold; color: orange; font-size: 14px;")
        self.layout.addWidget(self.status_label)
        
        # Text Output (Recovered Data)
        self.text_out = Qt.QTextEdit()
        self.text_out.setReadOnly(True)
        self.text_out.setPlaceholderText("Recovered messages will appear here...")
        self.layout.addWidget(self.text_out)

        # ----------------------------------------------------------------------
        # NODES SETUP
        # ----------------------------------------------------------------------
        self.session_a = session_manager(initial_seed=0xACE)
        self.pkt_a = packetizer()
        self.session_b = session_manager(initial_seed=0xACE)
        self.depkt_b = depacketizer()

        # ----------------------------------------------------------------------
        # TRANSMITTER CHAIN (NODE A)
        # ----------------------------------------------------------------------
        payload = "Opal Vanguard Mission 2026 - FHSS Secure Link"
        self.pdu_src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(payload), list(payload.encode()))), 1000)
        
        self.p2s_a = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        # GFSK parameters (h=1.0, BT=0.35)
        mod_sensitivity = (np.pi * 1.0) / 8.0
        self.mod_a = digital.gfsk_mod(samples_per_symbol=8, sensitivity=mod_sensitivity, bt=0.35)
        self.throttle = blocks.throttle(gr.sizeof_gr_complex, self.samp_rate)
        
        self.hop_ctrl = lfsr_hop_generator(seed=0xACE, center_freq=center_freq, num_channels=50, channel_spacing=100e3)
        self.rot_tx = blocks.rotator_cc(0)
        
        # ----------------------------------------------------------------------
        # RECEIVER CHAIN (NODE B)
        # ----------------------------------------------------------------------
        self.rot_rx = blocks.rotator_cc(0)
        self.demod_b = digital.gfsk_demod(samples_per_symbol=8, gain_mu=0.1, mu=0.5, omega_relative_limit=0.005, freq_error=0.0)

        # ----------------------------------------------------------------------
        # MESSAGE HANDLERS
        # ----------------------------------------------------------------------
        self.freq_handler = FreqHandlerBlock(self)
        self.status_handler = StatusHandlerBlock(self)
        self.data_handler = DataHandlerBlock(self)

        self.status_signal.connect(self.on_status_change)
        self.data_signal.connect(self.on_data_received)

        # ----------------------------------------------------------------------
        # VISUAL SINKS
        # ----------------------------------------------------------------------
        self.snk_waterfall = qtgui.waterfall_sink_c(2048, fft.window.WIN_BLACKMAN_HARRIS, 0, self.samp_rate, "FHSS Spectrum (915MHz Band)", 1)
        self.snk_rx_freq = qtgui.freq_sink_c(2048, fft.window.WIN_BLACKMAN_HARRIS, 0, self.samp_rate, "De-hopped Baseband (Node B)", 1)

        self.layout.addWidget(sip.wrapinstance(self.snk_waterfall.qwidget(), Qt.QWidget))
        self.layout.addWidget(sip.wrapinstance(self.snk_rx_freq.qwidget(), Qt.QWidget))

        # ----------------------------------------------------------------------
        # CONNECTIONS
        # ----------------------------------------------------------------------
        # A -> B RF Path
        self.msg_connect((self.pdu_src, "strobe"), (self.session_a, "data_in"))
        self.msg_connect((self.session_a, "pkt_out"), (self.pkt_a, "in"))
        self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
        self.connect(self.p2s_a, self.mod_a, self.demod_b)
        
        # Node B Receive
        self.connect(self.demod_b, self.depkt_b)
        self.msg_connect((self.depkt_b, "out"), (self.session_b, "msg_in"))
        
        # Handshake Return (B -> A)
        self.msg_connect((self.session_b, "pkt_out"), (self.session_a, "msg_in"))

        # Message logic connections
        self.msg_connect((self.hop_ctrl, "freq"), (self.freq_handler, "msg"))
        self.msg_connect((self.session_a, "pkt_out"), (self.status_handler, "msg"))
        self.msg_connect((self.session_b, "pkt_out"), (self.status_handler, "msg"))
        self.msg_connect((self.session_b, "data_out"), (self.data_handler, "msg"))

        # Visualization
        # Use a separate throttle for visualization to keep it from affecting the core processing
        self.viz_throttle = blocks.throttle(gr.sizeof_gr_complex, self.samp_rate)
        self.connect(self.mod_a, self.viz_throttle)
        self.connect(self.viz_throttle, self.snk_waterfall)
        self.connect(self.viz_throttle, self.snk_rx_freq)

        # Timer for frequency hops (every 200ms)
        self.timer = Qt.QTimer()
        self.timer.timeout.connect(lambda: self.hop_ctrl.handle_trigger(pmt.PMT_T))
        self.timer.start(200)

    def on_status_change(self, state_a, state_b):
        self.status_label.setText(f"Node A: {state_a} | Node B: {state_b}")
        if state_a == "CONNECTED" and state_b == "CONNECTED":
            self.status_label.setStyleSheet("font-weight: bold; color: green; font-size: 14px;")
        else:
            self.status_label.setStyleSheet("font-weight: bold; color: orange; font-size: 14px;")

    def on_data_received(self, payload):
        self.text_out.append(f"<b>[NODE B RX]:</b> {payload}")

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
