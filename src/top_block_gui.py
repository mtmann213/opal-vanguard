#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Full Loopback Visual Demo (TX & RX)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, analog, digital, qtgui, filter, fft
import pmt
from PyQt5 import Qt
import sip

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer
from whitener import whitener
from hop_controller import lfsr_hop_generator

class OpalVanguardVisualDemo(gr.top_block, Qt.QWidget):
    def __init__(self, samp_rate=2e6, center_freq=915e6):
        gr.top_block.__init__(self, "Opal Vanguard Full Loopback")
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Opal Vanguard - Full FHSS Loopback")
        
        self.samp_rate = samp_rate
        self.center_freq = center_freq

        # Layout Setup
        self.layout = Qt.QVBoxLayout()
        self.setLayout(self.layout)
        
        # Text Output (Recovered Data)
        self.text_out = Qt.QTextEdit()
        self.text_out.setReadOnly(True)
        self.text_out.setPlaceholderText("Recovered messages will appear here...")
        self.layout.addWidget(self.text_out)

        # ----------------------------------------------------------------------
        # TRANSMITTER SECTION
        # ----------------------------------------------------------------------
        # PDU Source: Generates "Opal Vanguard" every 1s
        payload = "Opal Vanguard Mission 2026"
        self.pdu_src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(payload), list(payload.encode()))), 1000)
        self.pkt = packetizer()
        self.pdu_to_stream = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        self.unpacker = blocks.unpack_k_bits_bb(8)
        self.whit_tx = whitener(seed=0x7F) # Whiten bits

        # GFSK Modulator
        self.gfsk_mod = digital.gfsk_mod(samples_per_symbol=8, sensitivity=1.0, bt=0.35)

        # FHSS Rotator (TX)
        self.hop_ctrl = lfsr_hop_generator(seed=0xACE, center_freq=center_freq, num_channels=50, channel_spacing=100e3)
        self.rot_tx = blocks.rotator_cc(0)
        
        # ----------------------------------------------------------------------
        # RECEIVER SECTION
        # ----------------------------------------------------------------------
        # FHSS Rotator (RX) - Inverts the frequency shift
        self.rot_rx = blocks.rotator_cc(0)
        
        # GFSK Demodulator
        self.gfsk_demod = digital.gfsk_demod(samples_per_symbol=8, gain_mu=0.175, mu=0.5, omega_relative_limit=0.005, freq_error=0.0)
        
        # De-whiten & Re-pack
        self.whit_rx = whitener(seed=0x7F) # XORing again de-whitens
        self.packer = blocks.pack_k_bits_bb(8)
        self.depkt = depacketizer()

        # ----------------------------------------------------------------------
        # SHARED LOGIC & CALLBACKS
        # ----------------------------------------------------------------------
        def handle_freq_msg(msg):
            freq = pmt.to_double(msg)
            offset = freq - self.center_freq
            phase_inc = 2 * np.pi * offset / self.samp_rate
            self.rot_tx.set_phase_inc(phase_inc)
            self.rot_rx.set_phase_inc(-phase_inc) # Counter-rotate for RX

        class FreqProxy(gr.sync_block):
            def __init__(self, callback):
                gr.sync_block.__init__(self, "FreqProxy", None, None)
                self.message_port_register_in(pmt.intern("msg"))
                self.set_msg_handler(pmt.intern("msg"), callback)
        
        self.proxy = FreqProxy(handle_freq_msg)
        self.msg_connect((self.hop_ctrl, "freq"), (self.proxy, "msg"))

        # GUI Update for Received PDUs
        def handle_received_pdu(msg):
            payload = bytes(pmt.u8vector_elements(pmt.cdr(msg))).decode('utf-8', 'ignore')
            self.text_out.append(f"<b>[RX]:</b> {payload}")
            
        self.rx_proxy = FreqProxy(handle_received_pdu)
        self.msg_connect((self.depkt, "out"), (self.rx_proxy, "msg"))

        # ----------------------------------------------------------------------
        # VISUAL SINKS
        # ----------------------------------------------------------------------
        self.snk_freq = qtgui.freq_sink_c(2048, fft.window.WIN_BLACKMAN_HARRIS, 0, self.samp_rate, "Transmitted Signal", 1)
        self.snk_waterfall = qtgui.waterfall_sink_c(2048, fft.window.WIN_BLACKMAN_HARRIS, 0, self.samp_rate, "Waterfall View", 1)
        self.snk_rx_freq = qtgui.freq_sink_c(2048, fft.window.WIN_BLACKMAN_HARRIS, 0, self.samp_rate, "De-hopped RX Signal", 1)

        self.layout.addWidget(sip.wrapinstance(self.snk_freq.qwidget(), Qt.QWidget))
        self.layout.addWidget(sip.wrapinstance(self.snk_waterfall.qwidget(), Qt.QWidget))
        self.layout.addWidget(sip.wrapinstance(self.snk_rx_freq.qwidget(), Qt.QWidget))

        # ----------------------------------------------------------------------
        # CONNECTIONS
        # ----------------------------------------------------------------------
        # TX Path
        self.msg_connect((self.pdu_src, "strobe"), (self.pkt, "in"))
        self.msg_connect((self.pkt, "out"), (self.pdu_to_stream, "pdus"))
        self.connect(self.pdu_to_stream, self.unpacker, self.whit_tx, self.gfsk_mod, self.rot_tx)
        
        # Channels (TX -> RX)
        self.connect(self.rot_tx, self.rot_rx)
        
        # RX Path
        self.connect(self.rot_rx, self.gfsk_demod, self.whit_rx, self.packer, self.depkt)

        # Visualization
        self.connect(self.rot_tx, self.snk_freq)
        self.connect(self.rot_tx, self.snk_waterfall)
        self.connect(self.rot_rx, self.snk_rx_freq)

        # Timer for frequency hops (every 200ms)
        self.timer = Qt.QTimer()
        self.timer.timeout.connect(lambda: self.hop_ctrl.handle_trigger(pmt.PMT_T))
        self.timer.start(200)

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
