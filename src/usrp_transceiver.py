#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Unified USRP Transceiver (Tactical Build v12.7)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, analog, digital, qtgui, filter, fft, uhd, pdu
import pmt
import time
import struct
import threading
import yaml
import argparse
from PyQt5 import Qt
from PyQt5.QtCore import pyqtSignal, QTimer, pyqtSlot
import sip

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer
from hop_generator_tod import tod_hop_generator
from session_manager import session_manager
from dsp_helper import CSSProcessor

class LoggerProxy:
    def __init__(self, original, log_file):
        self.original = original; self.log_file = log_file
    def write(self, data):
        if len(data) < 2: return # Filter out micro-writes
        self.original.write(data); self.log_file.write(data)
    def flush(self):
        self.original.flush(); self.log_file.flush()

class MessageProxy(gr.basic_block):
    def __init__(self, signal_emitter, port_name="msg"):
        gr.basic_block.__init__(self, "MessageProxy", None, None)
        self.message_port_register_in(pmt.intern(port_name))
        self.signal = signal_emitter
        self.set_msg_handler(pmt.intern(port_name), self.handle)
    def handle(self, msg):
        # Fire-and-forget signal to the UI thread
        self.signal.emit(msg)
    def work(self, i, o): return 0

class OpalVanguardUSRP(gr.top_block, Qt.QWidget):
    status_ui_sig = pyqtSignal(object)
    data_ui_sig = pyqtSignal(object)
    diag_ui_sig = pyqtSignal(object)

    def __init__(self, role="ALPHA", serial="", config_path="mission_configs/level1_soft_link.yaml"):
        self.log_filename = f"mission_{role}.log"
        self.log_f = open(self.log_filename, "a", buffering=1)
        sys.stdout = LoggerProxy(sys.stdout, self.log_f)
        sys.stderr = LoggerProxy(sys.stderr, self.log_f)
        
        self.role, self.serial, self.config_path = role, serial, config_path
        with open(config_path, 'r') as f: self.cfg = yaml.safe_load(f)
        mission_id = self.cfg.get('mission', {}).get('id', 'UNKNOWN')
        
        print(f"\n--- [OPAL VANGUARD {role} START: {time.ctime()} | MISSION: {mission_id}] ---")

        gr.top_block.__init__(self, f"Opal Vanguard - {role} [{mission_id}]")
        Qt.QWidget.__init__(self)
        self.setWindowTitle(f"Opal Vanguard - {role} [{mission_id}]")
        p_cfg, h_cfg, hw_cfg = self.cfg['physical'], self.cfg['hopping'], self.cfg['hardware']
        l_cfg = self.cfg['link_layer']
        
        self.samp_rate = hw_cfg.get('samp_rate', 2000000)
        self.center_freq = p_cfg.get('center_freq', 915000000)
        self.payload_type = self.cfg.get('application_layer', {}).get('payload_type', 'heartbeat')

        self.setup_ui(role, serial, hw_cfg)
        self.setup_hardware(hw_cfg, serial)
        self.manual_queue = [] # Thread-safe queue for UI-to-Radio data
        self.setup_dsp(config_path, h_cfg, p_cfg, l_cfg)
        self.connect_logic(mod_type=p_cfg.get('modulation', 'GFSK'), h_cfg=h_cfg)

    def setup_ui(self, role, serial, hw_cfg):
        mission_id = self.cfg.get('mission', {}).get('id', 'UNKNOWN')
        self.setWindowTitle(f"Opal Vanguard - {role} [{mission_id}]")
        self.main_layout = Qt.QVBoxLayout(); self.setLayout(self.main_layout)
        self.info_label = Qt.QLabel(f"<b>NODE: {role} | SDR: {serial} | MISSION: {mission_id}</b>")
        self.info_label.setStyleSheet("color: #00ffcc; font-size: 14px;")
        self.status_label = Qt.QLabel("Status: IDLE"); self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        self.main_layout.addWidget(self.info_label); self.main_layout.addWidget(self.status_label)

        # Tactical Operations Center (TOC) - Single Screen Unified Display
        self.toc_group = Qt.QGroupBox("Tactical Operations Center (TOC)")
        self.toc_layout = Qt.QGridLayout(self.toc_group)
        self.main_layout.addWidget(self.toc_group)
        
        # Zone A: Signal Integrity & LQI History (Top Row, Spans both columns)
        self.health_group = Qt.QGroupBox("Tactical Signal Integrity (LQI)")
        self.health_layout = Qt.QVBoxLayout(self.health_group) # Vertical stack for full width
        self.toc_layout.addWidget(self.health_group, 0, 0, 1, 2)

        self.conf_bar = Qt.QProgressBar(); self.conf_bar.setRange(0, 100)
        self.health_layout.addWidget(Qt.QLabel("LQI (Signal Confidence %):")); self.health_layout.addWidget(self.conf_bar)
        
        self.status_row = Qt.QHBoxLayout()
        self.crc_led = Qt.QLabel("CRC: ---"); self.fec_count = Qt.QLabel("FEC: 0")
        self.afh_label = Qt.QLabel("AFH: [CLEAR]"); self.afh_label.setStyleSheet("color: #00FF00; font-weight: bold;")
        self.status_row.addWidget(self.crc_led); self.status_row.addWidget(self.fec_count); self.status_row.addWidget(self.afh_label)
        self.health_layout.addLayout(self.status_row)
        
        self.lqi_history_list = Qt.QListWidget()
        self.lqi_history_list.setMaximumHeight(120) 
        self.health_layout.addWidget(self.lqi_history_list)

        # Zone B: Spectrum Analysis (Middle Row, Spans both columns)
        self.viz_panel = Qt.QVBoxLayout()
        self.toc_layout.addLayout(self.viz_panel, 1, 0, 1, 2)

        # Zone C: Hardware Controls (New Full-Width Horizontal Bar)
        self.hw_group = Qt.QGroupBox("Hardware Gain Control")
        self.hw_layout = Qt.QHBoxLayout(self.hw_group) # Horizontal for wide look
        self.toc_layout.addWidget(self.hw_group, 2, 0, 1, 2)
        
        self.tx_gain_slider = Qt.QSlider(Qt.Qt.Horizontal); self.tx_gain_slider.setRange(0, 90); self.tx_gain_slider.setValue(hw_cfg.get('tx_gain', 70))
        self.rx_gain_slider = Qt.QSlider(Qt.Qt.Horizontal); self.rx_gain_slider.setRange(0, 90); self.rx_gain_slider.setValue(hw_cfg.get('rx_gain', 70))
        self.hw_layout.addWidget(Qt.QLabel("TX:")); self.hw_layout.addWidget(self.tx_gain_slider)
        self.hw_layout.addWidget(Qt.QLabel("RX:")); self.hw_layout.addWidget(self.rx_gain_slider)
        self.tx_gain_slider.valueChanged.connect(lambda v: self.usrp_sink.set_gain(v, 0)); self.rx_gain_slider.valueChanged.connect(lambda v: self.usrp_source.set_gain(v, 0))

        # Zone D: Tactical Feed & BFT (Bottom Row, Spans both columns)
        self.feed_group = Qt.QGroupBox("Tactical Feed & BFT Tracking")
        self.feed_layout = Qt.QVBoxLayout(self.feed_group)
        self.toc_layout.addWidget(self.feed_group, 3, 0, 1, 2)
        
        self.text_out = Qt.QTextEdit(); self.text_out.setReadOnly(True); self.feed_layout.addWidget(self.text_out)
        self.target_table = Qt.QTableWidget(5, 4)
        self.target_table.setHorizontalHeaderLabels(["ID", "Role", "Lat/Lon", "Last Seen"])
        self.target_table.horizontalHeader().setSectionResizeMode(Qt.QHeaderView.Stretch)
        self.target_table.setMaximumHeight(150)
        self.feed_layout.addWidget(self.target_table)

        # Chat Input (Always initialized, hidden if not in chat mode)
        self.chat_layout = Qt.QHBoxLayout(); self.chat_input = Qt.QLineEdit(); self.chat_btn = Qt.QPushButton("Send")
        self.chat_layout.addWidget(self.chat_input); self.chat_layout.addWidget(self.chat_btn); self.feed_layout.addLayout(self.chat_layout)
        self.chat_btn.clicked.connect(self.send_chat); self.chat_input.returnPressed.connect(self.send_chat)
        if self.payload_type != 'chat': self.chat_input.setPlaceholderText("BFT Command Entry (e.g. BFT|ID|ROLE|COORDS)")

        self.status_ui_sig.connect(self.on_status_msg)
        self.data_ui_sig.connect(self.on_data_msg)
        self.diag_ui_sig.connect(self.on_diag_msg)

    def setup_hardware(self, hw_cfg, serial):
        args = hw_cfg['args'] + (f",serial={serial}" if serial else "")
        try:
            self.usrp_sink = uhd.usrp_sink(args, uhd.stream_args(cpu_format="fc32", channels=[0]), "packet_len")
            self.usrp_source = uhd.usrp_source(args, uhd.stream_args(cpu_format="fc32", channels=[0]))
            for dev in [self.usrp_sink, self.usrp_source]:
                dev.set_clock_source("internal"); dev.set_time_source("internal")
                dev.set_samp_rate(self.samp_rate); dev.set_center_freq(self.center_freq, 0)
            self.usrp_sink.set_gain(hw_cfg['tx_gain'], 0); self.usrp_source.set_gain(hw_cfg['rx_gain'], 0)
            # v19.18: Hard reset hardware clock to 0.0 for clean burst-tagging
            self.usrp_sink.set_time_now(uhd.time_spec(0.0))
            print(f"[HW] USRP {serial} Initialized (Stealth Mode Active).")
        except Exception as e: print(f"FATAL HW ERROR: {e}"); sys.exit(1)

    def setup_dsp(self, config_path, h_cfg, p_cfg, l_cfg):
        sid = 1 if self.role == "ALPHA" else 2
        self.session = session_manager(initial_seed=h_cfg.get('initial_seed', 0xACE), config_path=config_path)
        self.pkt_a = packetizer(config_path=config_path, src_id=sid)
        self.depkt_b = depacketizer(config_path=config_path, src_id=sid, ignore_self=True)
        
        if l_cfg.get('use_comsec', False):
            key = bytes.fromhex(l_cfg.get('comsec_key', '00'*32))
            self.pkt_a.use_comsec = True; self.pkt_a.comsec_key = key
            self.depkt_b.use_comsec = True; self.depkt_b.comsec_key = key

        self.p2s_a = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        self.mac_strobe = blocks.message_strobe(pmt.PMT_T, 1000)
        
        if self.payload_type == 'heartbeat':
            hb_msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(f"PING FROM {self.role}"), list(f"PING FROM {self.role}".encode())))
            # v19.29: Adaptive Handshake Strobe. Level 6+ uses 1000ms to avoid TX saturation.
            strobe_ms = 1000 if "LEVEL_6" in config_path or "LEVEL_7" in config_path else 200
            self.pdu_src = blocks.message_strobe(hb_msg, strobe_ms)
        else:
            self.pdu_src = blocks.message_debug()

        sps = p_cfg.get('samples_per_symbol', 10)
        # v19.36: Bit-Domain Scaling. Pre-calculates the final sample count for the USRP Sink.
        self.mult_len = blocks.tagged_stream_multiply_length(gr.sizeof_char, "packet_len", sps)
        
        mod_type = p_cfg.get('modulation', 'GFSK')
        print(f"\n[DSP] Mode: {mod_type} | SPS: {sps} | Rate: {self.samp_rate/1e6:.1f} Msps")
        print(f"[DSP] Preamble: {p_cfg.get('preamble_len', 1024)} bits | Frame: {l_cfg.get('frame_size', 120)} bytes")
        
        if mod_type in ["GFSK", "MSK", "GMSK"]:
            bit_rate = self.samp_rate / sps
            default_dev = bit_rate / 4.0 if mod_type in ["MSK", "GMSK"] else p_cfg.get('freq_dev', 25000)
            sens = (2.0 * np.pi * default_dev) / self.samp_rate
            # v19.27: Standard MSK (BT=0.5) for improved hardware sensitivity
            bt = 0.5 if mod_type == "MSK" else p_cfg.get('gmsk_bt', 0.35)
            self.mod_a = digital.gfsk_mod(sps, sens, bt, False, False, False)
            # v19.31: Restored original stable clock recovery parameters
            self.demod_b = digital.gfsk_demod(sps, sens, 0.1, 0.5, 0.005, 0.0)
        elif mod_type == "DQPSK":
            self.mod_a = digital.psk_mod(4, differential=True, samples_per_symbol=sps, excess_bw=0.35)
            self.demod_b = digital.psk_demod(4, differential=True, samples_per_symbol=sps, excess_bw=0.35)
        elif mod_type == "OFDM":
            self.mod_a = digital.ofdm_tx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
            self.demod_b = digital.ofdm_rx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
            self.unpack = blocks.packed_to_unpacked_bb(1, gr.GR_MSB_FIRST)
        elif mod_type == "CSS":
            self.css_p = CSSProcessor(sps=p_cfg.get('samples_per_symbol', 128), samp_rate=self.samp_rate)
            # Optimized Rate-Changing Python Blocks
            class CSSMod(gr.interp_block):
                def __init__(self, p): gr.interp_block.__init__(self, "CSSMod", in_sig=[np.uint8], out_sig=[np.complex64], interpolation=p.sps); self.p = p
                def work(self, i, o):
                    res = self.p.modulate(i[0])
                    o[0][:len(res)] = res
                    return len(res)
            class CSSDemod(gr.decim_block):
                def __init__(self, p): gr.decim_block.__init__(self, "CSSDemod", in_sig=[np.complex64], out_sig=[np.uint8], decimation=p.sps); self.p = p
                def work(self, i, o):
                    b, _ = self.p.demodulate(i[0])
                    o[0][:len(b)] = b
                    return len(b)
            self.mod_a, self.demod_b = CSSMod(self.css_p), CSSDemod(self.css_p)

        self.rx_filter = filter.fir_filter_ccf(1, filter.firdes.low_pass(1.0, self.samp_rate, 250e3, 50e3))
        self.hop_ctrl = tod_hop_generator(key=bytes.fromhex(h_cfg.get('aes_key', '00'*32)), num_channels=h_cfg.get('num_channels', 50), center_freq=self.center_freq, channel_spacing=h_cfg.get('channel_spacing', 150000), dwell_ms=h_cfg.get('dwell_time_ms', 500))

    def connect_logic(self, mod_type, h_cfg):
        self.diag_proxy = MessageProxy(self.diag_ui_sig)
        self.status_proxy = MessageProxy(self.status_ui_sig)
        self.data_proxy = MessageProxy(self.data_ui_sig)

        # UI-to-Radio Thread Bridge (Ensures UI never blocks on radio operations)
        class UIBridge(gr.basic_block):
            def __init__(self, queue, target_block):
                gr.basic_block.__init__(self, "UIBridge", None, None); self.q = queue; self.target = target_block
                self.message_port_register_in(pmt.intern("poll")); self.set_msg_handler(pmt.intern("poll"), self.handle)
            def handle(self, msg):
                if self.q:
                    try: data = self.q.pop(0); self.target.post(pmt.intern("manual_in"), data)
                    except: pass
            def work(self, i, o): return 0
        
        self.ui_bridge = UIBridge(self.manual_queue, self.session)
        self.bridge_strobe = blocks.message_strobe(pmt.PMT_T, 50) # Poll queue every 50ms
        self.msg_connect((self.bridge_strobe, "strobe"), (self.ui_bridge, "poll"))

        self.msg_connect((self.mac_strobe, "strobe"), (self.session, "heartbeat"))
        src_port = "out" if self.payload_type == 'chat' else "strobe"
        self.msg_connect((self.pdu_src, src_port), (self.session, "data_in"))
        self.msg_connect((self.session, "pkt_out"), (self.pkt_a, "in"))
        self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
        
        if mod_type == "OFDM":
            self.connect(self.p2s_a, self.mod_a, self.usrp_sink)
            self.connect(self.usrp_source, self.rx_filter, self.demod_b, self.unpack, self.depkt_b)
        elif mod_type == "CSS":
            # CSS handles its own tag scaling via interp_block
            self.connect(self.p2s_a, self.mod_a, self.usrp_sink)
            self.connect(self.usrp_source, self.rx_filter, self.demod_b, self.depkt_b)
        else:
            self.connect(self.p2s_a, self.mult_len, self.mod_a, self.usrp_sink)
            self.connect(self.usrp_source, self.rx_filter, self.demod_b, self.depkt_b)

        self.msg_connect((self.depkt_b, "out"), (self.session, "msg_in"))
        self.msg_connect((self.depkt_b, "diagnostics"), (self.session, "msg_in"))
        self.msg_connect((self.depkt_b, "diagnostics"), (self.diag_proxy, "msg"))
        self.msg_connect((self.session, "status_out"), (self.status_proxy, "msg"))
        self.msg_connect((self.session, "data_out"), (self.data_proxy, "msg"))
        
        # Phase 14: Cognitive AFH Loop
        self.msg_connect((self.hop_ctrl, "freq"), (self.session, "freq_in"))
        self.msg_connect((self.session, "afh_out"), (self.hop_ctrl, "blacklist"))

        # GUI Optimization: 512-point FFT at 10 FPS for L6
        fft_size = 512 if "LEVEL_6" in self.cfg['mission']['id'] else 1024
        fps_delay = 0.1 if "LEVEL_6" in self.cfg['mission']['id'] else 0.06
        self.snk_waterfall = qtgui.waterfall_sink_c(fft_size, fft.window.WIN_BLACKMAN_HARRIS, self.center_freq, self.samp_rate, "Tactical Display", 1)
        self.snk_waterfall.set_update_time(fps_delay) 
        self.viz_panel.addWidget(sip.wrapinstance(self.snk_waterfall.qwidget(), Qt.QWidget))
        self.connect(self.usrp_source, self.snk_waterfall)

        # Tuning Handler (Untimed Immediate Mode)
        class UHDHandler(gr.basic_block):
            def __init__(self, usrp_src, usrp_snk, initial_f):
                gr.basic_block.__init__(self, "UHDHandler", None, None); self.src, self.snk = usrp_src, usrp_snk
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
                self.last_f = initial_f
            def handle(self, msg):
                try:
                    # Correct Extraction for PMT Double (v19.12)
                    f = pmt.to_double(msg)
                    if f > 0 and f != self.last_f:
                        # Direct Immediate Tune
                        self.snk.set_center_freq(f, 0)
                        self.src.set_center_freq(f, 0)
                        self.last_f = f
                except: pass
            def work(self, i, o): return 0
        self.uhd_h = UHDHandler(self.usrp_source, self.usrp_sink, self.center_freq)
        self.msg_connect((self.hop_ctrl, "freq"), (self.uhd_h, "msg"))

        self.timer = QTimer(); self.timer.timeout.connect(lambda: self.hop_ctrl.handle_trigger(pmt.PMT_T))
        if h_cfg.get('enabled', True): self.timer.start(h_cfg['dwell_time_ms'])

    @pyqtSlot(object)
    def on_status_msg(self, msg):
        try:
            s = pmt.to_python(pmt.dict_ref(msg, pmt.intern("state"), pmt.from_long(0)))
            self.status_label.setText(f"Status: {s}")
            self.status_label.setStyleSheet(f"color: {'green' if s == 'CONNECTED' else 'orange'}; font-weight: bold;")
            print(f"[STATUS] {s}", flush=True)
            
            # Safely handle Blacklist if present
            if pmt.dict_has_key(msg, pmt.intern("blacklist")):
                bl = list(pmt.to_python(pmt.dict_ref(msg, pmt.intern("blacklist"), pmt.make_vector(0, pmt.PMT_NIL))))
                if bl:
                    self.afh_label.setText(f"AFH EVADED: {bl}")
                    self.afh_label.setStyleSheet("color: #FFA500; font-weight: bold;")
                else:
                    self.afh_label.setText("AFH: [CLEAR]")
                    self.afh_label.setStyleSheet("color: #00FF00; font-weight: bold;")
        except: pass

    @pyqtSlot(object)
    def on_data_msg(self, msg):
        try:
            raw = bytes(pmt.u8vector_elements(pmt.cdr(msg))).decode('utf-8', errors='replace')
            print(f"[RX] {raw}", flush=True)
            if raw.startswith("BFT|"):
                # Format: BFT|ID|ROLE|LAT,LON
                parts = raw.split("|")
                if len(parts) >= 4:
                    row = int(parts[1]) % 5 # Map to table row
                    self.target_table.setItem(row, 0, Qt.QTableWidgetItem(parts[1]))
                    self.target_table.setItem(row, 1, Qt.QTableWidgetItem(parts[2]))
                    self.target_table.setItem(row, 2, Qt.QTableWidgetItem(parts[3]))
                    self.target_table.setItem(row, 3, Qt.QTableWidgetItem(time.strftime("%H:%M:%S")))
            else:
                self.text_out.append(f"<b>[RX]:</b> {raw}")
        except: pass

    @pyqtSlot(object)
    def on_diag_msg(self, msg):
        try:
            conf = pmt.to_double(pmt.dict_ref(msg, pmt.intern("confidence"), pmt.from_double(0)))
            repairs = pmt.to_long(pmt.dict_ref(msg, pmt.intern("fec_repairs"), pmt.from_long(0)))
            ok = pmt.to_bool(pmt.dict_ref(msg, pmt.intern("crc_ok"), pmt.from_bool(False)))
            
            # Update Main UI
            self.conf_bar.setValue(int(conf))
            self.crc_led.setText(f"CRC: {'OK' if ok else 'FAIL'}")
            self.crc_led.setStyleSheet(f"color: {'green' if ok else 'red'}; font-weight: bold;")
            self.fec_count.setText(f"FEC Repairs: {repairs}")
            
            # Update Tactical History
            ts = time.strftime("%H:%M:%S")
            self.lqi_history_list.insertItem(0, f"[{ts}] LQI: {conf:.1f}% | Repairs: {repairs} | CRC: {'OK' if ok else 'FAIL'}")
            if self.lqi_history_list.count() > 50: self.lqi_history_list.takeItem(50)
        except: pass

    def send_chat(self):
        txt = self.chat_input.text()
        if txt:
            self.text_out.append(f"<b>[SENT]:</b> {txt}")
            # PUSH to async queue. Radio thread will poll this and send.
            msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(txt), list(txt.encode())))
            self.manual_queue.append(msg)
            self.chat_input.clear()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", default="ALPHA")
    parser.add_argument("--serial", default="")
    parser.add_argument("--config", default="mission_configs/level1_soft_link.yaml")
    args = parser.parse_args()
    qapp = Qt.QApplication(sys.argv)
    tb = OpalVanguardUSRP(args.role, args.serial, args.config)
    tb.start(); tb.show(); qapp.exec_()

if __name__ == '__main__': main()
