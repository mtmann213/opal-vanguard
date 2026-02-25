#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Full Loopback Visual Demo (with Session Management)

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

class OpalVanguardVisualDemo(gr.top_block, Qt.QWidget):
    status_signal = pyqtSignal(str, str)
    data_signal = pyqtSignal(str)

    def __init__(self, samp_rate=2e6, center_freq=915e6):
        gr.top_block.__init__(self, "Opal Vanguard Full Loopback")
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Opal Vanguard - Full FHSS Handshake Demo")
        
        self.status_signal.connect(self.on_status_change)
        self.data_signal.connect(self.on_data_received)
        
        self.samp_rate = samp_rate
        self.center_freq = center_freq

        # Layout Setup
        self.layout = Qt.QVBoxLayout()
        self.setLayout(self.layout)
        
        # Status Display
        self.status_label = Qt.QLabel("System Status: Initializing...")
        self.status_label.setStyleSheet("font-weight: bold; color: blue;")
        self.layout.addWidget(self.status_label)
        
        # Text Output (Recovered Data)
        self.text_out = Qt.QTextEdit()
        self.text_out.setReadOnly(True)
        self.text_out.setPlaceholderText("Recovered messages will appear here...")
        self.layout.addWidget(self.text_out)

        # ----------------------------------------------------------------------
        # NODES SETUP
        # ----------------------------------------------------------------------
        # NODE A (Master/TX)
        self.session_a = session_manager(initial_seed=0xACE)
        self.pkt_a = packetizer()
        
        # NODE B (Slave/RX)
        self.session_b = session_manager(initial_seed=0xACE)
        self.depkt_b = depacketizer()

        # ----------------------------------------------------------------------
        # TRANSMITTER CHAIN (NODE A)
        # ----------------------------------------------------------------------
        # PDU Source: Generates mission data every 2s
        payload = "Opal Vanguard Mission 2026 - FHSS Secure Link"
        self.pdu_src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(payload), list(payload.encode()))), 2000)
        
        self.p2s_a = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        self.unp_a = blocks.unpack_k_bits_bb(8)
        self.mod_a = digital.gfsk_mod(samples_per_symbol=8, sensitivity=1.0, bt=0.35)
        
        # FHSS Rotator (TX)
        self.hop_ctrl = lfsr_hop_generator(seed=0xACE, center_freq=center_freq, num_channels=50, channel_spacing=100e3)
        self.rot_tx = blocks.rotator_cc(0)
        
        # ----------------------------------------------------------------------
        # RECEIVER CHAIN (NODE B)
        # ----------------------------------------------------------------------
        self.rot_rx = blocks.rotator_cc(0)
        self.demod_b = digital.gfsk_demod(samples_per_symbol=8, gain_mu=0.175, mu=0.5, omega_relative_limit=0.005, freq_error=0.0)
        self.pack_b = blocks.pack_k_bits_bb(8)

        # ----------------------------------------------------------------------
        # HANDSHAKE & SHARED LOGIC
        # ----------------------------------------------------------------------
        # Freq Control Callback
        def handle_freq_msg(msg):
            freq = pmt.to_double(msg)
            offset = freq - self.center_freq
            phase_inc = 2 * np.pi * offset / self.samp_rate
            self.rot_tx.set_phase_inc(phase_inc)
            self.rot_rx.set_phase_inc(-phase_inc)

        class MsgProxy(gr.sync_block):
            def __init__(self, callback):
                gr.sync_block.__init__(self, "MsgProxy", None, None)
                self.message_port_register_in(pmt.intern("msg"))
                self.set_msg_handler(pmt.intern("msg"), callback)
        
        self.freq_proxy = MsgProxy(handle_freq_msg)
        self.msg_connect((self.hop_ctrl, "freq"), (self.freq_proxy, "msg"))

        # Status Update Callback
        def update_status(msg):
            # Safe way to update the GUI from the GR thread
            self.status_signal.emit(self.session_a.state, self.session_b.state)

        self.status_proxy = MsgProxy(update_status)
        # Trigger status update on any packet activity
        self.msg_connect((self.session_a, "pkt_out"), (self.status_proxy, "msg"))
        self.msg_connect((self.session_b, "pkt_out"), (self.status_proxy, "msg"))

        # RX Data Display Callback
        def handle_received_data(msg):
            payload = bytes(pmt.u8vector_elements(pmt.cdr(msg))).decode('utf-8', 'ignore')
            self.data_signal.emit(payload)
            
        self.data_proxy = MsgProxy(handle_received_data)
        self.msg_connect((self.session_b, "data_out"), (self.data_proxy, "msg"))

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
        # A -> B RF Path (Modulated)
        self.msg_connect((self.pdu_src, "strobe"), (self.session_a, "data_in"))
        self.msg_connect((self.session_a, "pkt_out"), (self.pkt_a, "in"))
        self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
        self.connect(self.p2s_a, self.unp_a, self.mod_a, self.rot_tx)
        
        # Channel
        self.connect(self.rot_tx, self.rot_rx)
        
        # Node B Receive
        self.connect(self.rot_rx, self.demod_b, self.pack_b, self.depkt_b)
        self.msg_connect((self.depkt_b, "out"), (self.session_b, "msg_in"))
        
        # B -> A Return Path (Simplified message loop for ACK)
        # In a real demo we'd modulate this too, but for handshake logic it's sufficient
        self.msg_connect((self.session_b, "pkt_out"), (self.session_a, "msg_in"))

        # Visualization
        self.connect(self.rot_tx, self.snk_waterfall)
        self.connect(self.rot_rx, self.snk_rx_freq)

        # Timer for frequency hops (every 200ms)
        self.timer = Qt.QTimer()
        self.timer.timeout.connect(lambda: self.hop_ctrl.handle_trigger(pmt.PMT_T))
        self.timer.start(200)

    def on_status_change(self, state_a, state_b):
        self.status_label.setText(f"Node A: {state_a} | Node B: {state_b}")
        if state_a == "CONNECTED" and state_b == "CONNECTED":
            self.status_label.setStyleSheet("font-weight: bold; color: green;")
        else:
            self.status_label.setStyleSheet("font-weight: bold; color: orange;")

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
