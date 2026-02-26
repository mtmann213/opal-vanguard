#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - USRP B210/B205mini Transceiver

import os
import sys
import numpy as np
from gnuradio import gr, blocks, analog, digital, qtgui, filter, fft, uhd
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
from hop_generator_tod import tod_hop_generator
from session_manager import session_manager

# ----------------------------------------------------------------------
# HARDWARE HANDLER BLOCK
# ----------------------------------------------------------------------
class UHDHandlerBlock(gr.basic_block):
    def __init__(self, parent):
        gr.basic_block.__init__(self, name="UHDHandler", in_sig=None, out_sig=None)
        self.parent = parent
        self.message_port_register_in(pmt.intern("msg"))
        self.set_msg_handler(pmt.intern("msg"), self.handle_freq)

    def handle_msg(self, msg):
        # Fallback for generic messages
        pass

    def handle_freq(self, msg):
        """Updates USRP center frequency for FHSS."""
        try:
            target_freq = pmt.to_double(msg)
            # We tune the USRP directly for hardware hopping
            tune_req = uhd.tune_request(target_freq)
            self.parent.usrp_sink.set_center_freq(tune_req)
            self.parent.usrp_source.set_center_freq(tune_req)
        except Exception as e:
            print(f"UHD Tune Error: {e}")

# ----------------------------------------------------------------------
# MAIN HARDWARE GUI CLASS
# ----------------------------------------------------------------------
class OpalVanguardUSRP(gr.top_block, Qt.QWidget):
    status_signal = pyqtSignal(str, str)
    data_signal = pyqtSignal(str)

    def __init__(self, config_path="config.yaml"):
        gr.top_block.__init__(self, "Opal Vanguard USRP")
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Opal Vanguard - USRP Hardware Terminal")
        
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
            
        hcfg = self.cfg['hopping']
        hw_cfg = self.cfg['hardware']
        self.samp_rate = hw_cfg['samp_rate']
        self.center_freq = self.cfg['physical']['center_freq']

        # Layout
        self.main_layout = Qt.QHBoxLayout(); self.setLayout(self.main_layout)
        self.ctrl_panel = Qt.QVBoxLayout(); self.main_layout.addLayout(self.ctrl_panel, 1)
        self.viz_panel = Qt.QVBoxLayout(); self.main_layout.addLayout(self.viz_panel, 3)
        
        # Status
        self.status_label = Qt.QLabel("Hardware Initializing...")
        self.status_label.setStyleSheet("font-weight: bold; color: blue; font-size: 14px;")
        self.ctrl_panel.addWidget(self.status_label)

        # Gain Controls
        self.ctrl_panel.addWidget(Qt.QLabel("<b>USRP Gain Control</b>"))
        
        self.tx_gain_label = Qt.QLabel(f"TX Gain: {hw_cfg['tx_gain']} dB")
        self.ctrl_panel.addWidget(self.tx_gain_label)
        self.tx_gain_slider = Qt.QSlider(Qt.Qt.Horizontal)
        self.tx_gain_slider.setRange(0, 90); self.tx_gain_slider.setValue(hw_cfg['tx_gain'])
        self.tx_gain_slider.valueChanged.connect(self.update_hardware)
        self.ctrl_panel.addWidget(self.tx_gain_slider)

        self.rx_gain_label = Qt.QLabel(f"RX Gain: {hw_cfg['rx_gain']} dB")
        self.ctrl_panel.addWidget(self.rx_gain_label)
        self.rx_gain_slider = Qt.QSlider(Qt.Qt.Horizontal)
        self.rx_gain_slider.setRange(0, 90); self.rx_gain_slider.setValue(hw_cfg['rx_gain'])
        self.rx_gain_slider.valueChanged.connect(self.update_hardware)
        self.ctrl_panel.addWidget(self.rx_gain_slider)

        self.text_out = Qt.QTextEdit(); self.text_out.setReadOnly(True); self.ctrl_panel.addWidget(self.text_out)

        # ----------------------------------------------------------------------
        # USRP HARDWARE SETUP
        # ----------------------------------------------------------------------
        try:
            # SINK (Transmitter)
            self.usrp_sink = uhd.usrp_sink(hw_cfg['args'], uhd.stream_args(cpu_format="fc32", channels=[0]))
            self.usrp_sink.set_samp_rate(self.samp_rate)
            self.usrp_sink.set_center_freq(self.center_freq, 0)
            self.usrp_sink.set_gain(hw_cfg['tx_gain'], 0)
            self.usrp_sink.set_antenna(hw_cfg['tx_antenna'], 0)

            # SOURCE (Receiver)
            self.usrp_source = uhd.usrp_source(hw_cfg['args'], uhd.stream_args(cpu_format="fc32", channels=[0]))
            self.usrp_source.set_samp_rate(self.samp_rate)
            self.usrp_source.set_center_freq(self.center_freq, 0)
            self.usrp_source.set_gain(hw_cfg['rx_gain'], 0)
            self.usrp_source.set_antenna(hw_cfg['rx_antenna'], 0)
        except Exception as e:
            print(f"FATAL: Could not initialize USRP: {e}")
            sys.exit(1)

        # ----------------------------------------------------------------------
        # NODES SETUP
        # ----------------------------------------------------------------------
        self.session_a = session_manager(initial_seed=hcfg['initial_seed'])
        self.session_b = session_manager(initial_seed=hcfg['initial_seed'])
        if hcfg['sync_mode'] == "TOD":
            self.session_a.state = "CONNECTED"; self.session_b.state = "CONNECTED"
            
        self.pkt_a = packetizer(config_path=config_path)
        self.depkt_b = depacketizer(config_path=config_path)

        # ----------------------------------------------------------------------
        # TRANSMITTER CHAIN
        # ----------------------------------------------------------------------
        payload = "Opal Vanguard USRP Mission Data"
        self.pdu_src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(payload), list(payload.encode()))), 3000)
        self.p2s_a = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        self.mod_a = digital.gfsk_mod(samples_per_symbol=8, sensitivity=(np.pi*1.0)/8.0, bt=0.35)
        
        # Hop Controller
        if hcfg['sync_mode'] == "TOD":
            self.hop_ctrl = tod_hop_generator(key=bytes.fromhex(hcfg['aes_key']), num_channels=hcfg['num_channels'], center_freq=self.center_freq, channel_spacing=hcfg['channel_spacing'], dwell_ms=hcfg['dwell_time_ms'], lookahead_ms=hcfg['lookahead_ms'])
        else:
            self.hop_ctrl = aes_hop_generator(key=bytes.fromhex(hcfg['aes_key']), num_channels=hcfg['num_channels'], center_freq=self.center_freq, channel_spacing=hcfg['channel_spacing'])
        
        # ----------------------------------------------------------------------
        # RECEIVER CHAIN
        # ----------------------------------------------------------------------
        lpf_taps = filter.firdes.low_pass(1.0, self.samp_rate, 500e3, 100e3) # Narrower filter for 2MHz samp_rate
        self.rx_filter = filter.fir_filter_ccf(1, lpf_taps)
        self.demod_b = digital.gfsk_demod(samples_per_symbol=8, gain_mu=0.1, mu=0.5, omega_relative_limit=0.005, freq_error=0.0)

        # ----------------------------------------------------------------------
        # HANDLERS & SIGNALS
        # ----------------------------------------------------------------------
        self.uhd_handler = UHDHandlerBlock(self)
        self.status_signal.connect(self.on_status_change)
        self.data_signal.connect(self.on_data_received)

        # ----------------------------------------------------------------------
        # VISUAL SINKS
        # ----------------------------------------------------------------------
        self.snk_waterfall = qtgui.waterfall_sink_c(2048, fft.window.WIN_BLACKMAN_HARRIS, self.center_freq, self.samp_rate, "USRP RF Spectrum", 1)
        self.viz_panel.addWidget(sip.wrapinstance(self.snk_waterfall.qwidget(), Qt.QWidget))

        # ----------------------------------------------------------------------
        # CONNECTIONS
        # ----------------------------------------------------------------------
        # TX Path: Session -> Packetizer -> GFSK -> USRP SINK
        self.msg_connect((self.pdu_src, "strobe"), (self.session_a, "data_in"))
        self.msg_connect((self.session_a, "pkt_out"), (self.pkt_a, "in"))
        self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
        self.connect(self.p2s_a, self.mod_a, self.usrp_sink)
        
        # RX Path: USRP SOURCE -> Filter -> Demod -> Depacketizer
        self.connect(self.usrp_source, self.rx_filter, self.demod_b, self.depkt_b)
        self.msg_connect((self.depkt_b, "out"), (self.session_b, "msg_in"))
        self.msg_connect((self.session_b, "pkt_out"), (self.session_a, "msg_in"))

        # Message logic
        self.msg_connect((self.hop_ctrl, "freq"), (self.uhd_handler, "msg"))
        self.msg_connect((self.session_b, "data_out"), (self.uhd_handler, "msg")) # Dummy to trigger something? No.
        
        # Custom logic to trigger GUI status updates
        class StatusProxy(gr.basic_block):
            def __init__(self, parent):
                gr.basic_block.__init__(self, "StatusProxy", None, None)
                self.parent = parent
                self.message_port_register_in(pmt.intern("msg"))
                self.set_msg_handler(pmt.intern("msg"), lambda msg: self.parent.status_signal.emit(self.parent.session_a.state, self.parent.session_b.state))
        
        self.sp = StatusProxy(self)
        self.msg_connect((self.session_a, "pkt_out"), (self.sp, "msg"))
        
        # Custom logic for RX text
        class DataProxy(gr.basic_block):
            def __init__(self, parent):
                gr.basic_block.__init__(self, "DataProxy", None, None)
                self.parent = parent
                self.message_port_register_in(pmt.intern("msg"))
                self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                payload = bytes(pmt.u8vector_elements(pmt.cdr(msg))).decode('utf-8', 'ignore')
                self.parent.data_signal.emit(payload)
        
        self.dp = DataProxy(self)
        self.msg_connect((self.session_b, "data_out"), (self.dp, "msg"))

        # Visualization
        self.connect(self.usrp_source, self.snk_waterfall)

        self.timer = Qt.QTimer()
        self.timer.timeout.connect(lambda: self.hop_ctrl.handle_trigger(pmt.PMT_T))
        self.timer.start(hcfg['dwell_time_ms'])

    def update_hardware(self):
        tx_g = self.tx_gain_slider.value()
        rx_g = self.rx_gain_slider.value()
        self.tx_gain_label.setText(f"TX Gain: {tx_g} dB")
        self.rx_gain_label.setText(f"RX Gain: {rx_g} dB")
        self.usrp_sink.set_gain(tx_g, 0)
        self.usrp_source.set_gain(rx_g, 0)

    def on_status_change(self, state_a, state_b):
        self.status_label.setText(f"USRP A: {state_a} | USRP B: {state_b}")
        if state_a == "CONNECTED": self.status_label.setStyleSheet("color: green;")

    def on_data_received(self, payload):
        self.text_out.append(f"<b>[RX]:</b> {payload}")

def main():
    qapp = Qt.QApplication(sys.argv)
    tb = OpalVanguardUSRP(); tb.start(); tb.show()
    def quitting(): tb.stop(); tb.wait()
    qapp.aboutToQuit.connect(quitting); qapp.exec_()

if __name__ == '__main__':
    main()
