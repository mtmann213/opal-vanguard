#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Unified USRP Transceiver (v15.8.15 Restoration)

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

class MessageProxy(gr.basic_block):
    def __init__(self, signal_emitter, port_name="msg"):
        gr.basic_block.__init__(self, "MessageProxy", None, None)
        self.message_port_register_in(pmt.intern(port_name))
        self.signal = signal_emitter
        self.set_msg_handler(pmt.intern(port_name), self.handle)
    def handle(self, msg):
        self.signal.emit(msg)
    def work(self, i, o): return 0

class OpalVanguardUSRP(gr.top_block, Qt.QWidget):
    status_ui_sig = pyqtSignal(object)
    data_ui_sig = pyqtSignal(object)
    diag_ui_sig = pyqtSignal(object)

    def __init__(self, role="ALPHA", serial="", config_path="mission_configs/level1_soft_link.yaml"):
        # v15.8.2: Standard Init Order
        Qt.QWidget.__init__(self)
        self.role, self.serial, self.config_path = role, serial, config_path
        with open(config_path, 'r') as f: self.cfg = yaml.safe_load(f)
        mission_id = self.cfg.get('mission', {}).get('id', 'UNKNOWN')
        gr.top_block.__init__(self, f"Opal Vanguard - {role} [{mission_id}]")
        
        print(f"\n--- [OPAL VANGUARD {role} START: {time.ctime()} | MISSION: {mission_id}] ---")

        p_cfg, h_cfg, hw_cfg = self.cfg['physical'], self.cfg['hopping'], self.cfg['hardware']
        l_cfg = self.cfg['link_layer']
        
        self.samp_rate = hw_cfg.get('samp_rate', 2000000)
        self.center_freq = p_cfg.get('center_freq', 915000000)
        self.payload_type = self.cfg.get('application_layer', {}).get('payload_type', 'heartbeat')

        self.setup_ui(role, serial, hw_cfg)
        self.setup_hardware(hw_cfg, serial)
        self.manual_queue = [] 
        self.setup_dsp(config_path, h_cfg, p_cfg, l_cfg)
        self.connect_logic(mod_type=p_cfg.get('modulation', 'GFSK'), h_cfg=h_cfg)

    def setup_ui(self, role, serial, hw_cfg):
        mission_id = self.cfg.get('mission', {}).get('id', 'UNKNOWN')
        self.setWindowTitle(f"Opal Vanguard - {role} [{mission_id}]")
        self.main_layout = Qt.QVBoxLayout(); self.setLayout(self.main_layout)
        self.info_label = Qt.QLabel(f"<b>MISSION: {mission_id} | NODE: {role} | SDR: {serial}</b>")
        self.status_label = Qt.QLabel("Status: IDLE"); self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        self.main_layout.addWidget(self.info_label); self.main_layout.addWidget(self.status_label)

        self.toc_group = Qt.QGroupBox("Tactical Operations Center (TOC)")
        self.toc_layout = Qt.QGridLayout(self.toc_group); self.main_layout.addWidget(self.toc_group)
        
        self.health_group = Qt.QGroupBox("Tactical Signal Integrity (LQI)")
        self.health_layout = Qt.QVBoxLayout(self.health_group); self.toc_layout.addWidget(self.health_group, 0, 0, 1, 2)
        self.conf_bar = Qt.QProgressBar(); self.conf_bar.setRange(0, 100)
        self.health_layout.addWidget(Qt.QLabel("LQI (Signal Confidence %):")); self.health_layout.addWidget(self.conf_bar)
        
        self.status_row = Qt.QHBoxLayout()
        self.crc_led = Qt.QLabel("CRC: ---"); self.fec_count = Qt.QLabel("FEC: 0")
        self.status_row.addWidget(self.crc_led); self.status_row.addWidget(self.fec_count)
        self.health_layout.addLayout(self.status_row)
        
        self.lqi_history_list = Qt.QListWidget(); self.lqi_history_list.setMaximumHeight(120) 
        self.health_layout.addWidget(self.lqi_history_list)

        self.viz_panel = Qt.QVBoxLayout(); self.toc_layout.addLayout(self.viz_panel, 1, 0, 1, 2)

        self.hw_group = Qt.QGroupBox("Hardware Gain Control")
        self.hw_layout = Qt.QHBoxLayout(self.hw_group); self.toc_layout.addWidget(self.hw_group, 2, 0, 1, 2)
        self.tx_gain_slider = Qt.QSlider(Qt.Qt.Horizontal); self.tx_gain_slider.setRange(0, 90); self.tx_gain_slider.setValue(hw_cfg.get('tx_gain', 70))
        self.rx_gain_slider = Qt.QSlider(Qt.Qt.Horizontal); self.rx_gain_slider.setRange(0, 90); self.rx_gain_slider.setValue(hw_cfg.get('rx_gain', 70))
        self.hw_layout.addWidget(Qt.QLabel("TX:")); self.hw_layout.addWidget(self.tx_gain_slider)
        self.hw_layout.addWidget(Qt.QLabel("RX:")); self.hw_layout.addWidget(self.rx_gain_slider)
        self.tx_gain_slider.valueChanged.connect(lambda v: self.usrp_sink.set_gain(v, 0)); self.rx_gain_slider.valueChanged.connect(lambda v: self.usrp_source.set_gain(v, 0))

        self.feed_group = Qt.QGroupBox("Tactical Feed & BFT Tracking")
        self.feed_layout = Qt.QVBoxLayout(self.feed_group); self.toc_layout.addWidget(self.feed_group, 3, 0, 1, 2)
        self.text_out = Qt.QTextEdit(); self.text_out.setReadOnly(True); self.feed_layout.addWidget(self.text_out)
        self.target_table = Qt.QTableWidget(5, 4)
        self.target_table.setHorizontalHeaderLabels(["ID", "Role", "Lat/Lon", "Last Seen"])
        self.target_table.horizontalHeader().setSectionResizeMode(Qt.QHeaderView.Stretch); self.target_table.setMaximumHeight(150)
        self.feed_layout.addWidget(self.target_table)

        self.chat_layout = Qt.QHBoxLayout(); self.chat_input = Qt.QLineEdit(); self.chat_btn = Qt.QPushButton("Send")
        self.chat_layout.addWidget(self.chat_input); self.chat_layout.addWidget(self.chat_btn); self.feed_layout.addLayout(self.chat_layout)
        self.chat_btn.clicked.connect(self.send_chat); self.chat_input.returnPressed.connect(self.send_chat)

        self.status_ui_sig.connect(self.on_status_msg)
        self.data_ui_sig.connect(self.on_data_msg)
        self.diag_ui_sig.connect(self.on_diag_msg)

    def setup_hardware(self, hw_cfg, serial):
        args = hw_cfg['args'] + (f",serial={serial}" if serial else "")
        try:
            self.usrp_sink = uhd.usrp_sink(args, uhd.stream_args(cpu_format="fc32", channels=[0]), "packet_len")
            self.usrp_source = uhd.usrp_source(args, uhd.stream_args(cpu_format="fc32", channels=[0]))
            for dev in [self.usrp_sink, self.usrp_source]:
                dev.set_samp_rate(self.samp_rate); dev.set_center_freq(self.center_freq, 0)
            self.usrp_sink.set_gain(hw_cfg['tx_gain'], 0); self.usrp_source.set_gain(hw_cfg['rx_gain'], 0)
            self.usrp_sink.set_time_now(uhd.time_spec(time.time()))
            print(f"[HW] USRP {serial} Clock Synced.")
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
            hb_interval = 100 if "LEVEL_6" in self.cfg['mission']['id'] else 1000
            self.pdu_src = blocks.message_strobe(hb_msg, hb_interval)
        else:
            self.pdu_src = blocks.message_debug()

        sps = p_cfg.get('samples_per_symbol', 10)
        # v15.8.17: Use native C++ scaling for maximum performance and to resolve tP errors.
        self.mult_len = blocks.tagged_stream_multiply_length(gr.sizeof_gr_complex, "packet_len", sps)
        
        mod_type = p_cfg.get('modulation', 'GFSK')
        if mod_type in ["GFSK", "MSK", "GMSK"]:
            bit_rate = self.samp_rate / sps
            default_dev = bit_rate / 4.0 if mod_type in ["MSK", "GMSK"] else p_cfg.get('freq_dev', 25000)
            sens = (2.0 * np.pi * default_dev) / self.samp_rate
            bt = 0.5 if mod_type == "MSK" else p_cfg.get('gmsk_bt', 0.35)
            self.mod_a = digital.gfsk_mod(sps, sens, bt, False, False, False)
            self.demod_b = digital.gfsk_demod(sps, sens, 0.1, 0.5, 0.005, 0.0)
        elif mod_type == "DBPSK":
            self.mod_a = digital.psk_mod(2, samples_per_symbol=sps, differential=True)
            self.demod_b = digital.psk_demod(2, samples_per_symbol=sps, differential=True)
        elif mod_type == "DQPSK":
            self.mod_a = digital.psk_mod(4, differential=True, samples_per_symbol=sps, excess_bw=0.35)
            self.demod_b = digital.psk_demod(4, differential=True, samples_per_symbol=sps, excess_bw=0.35)
        elif mod_type == "OFDM":
            self.mod_a = digital.ofdm_tx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
            self.demod_b = digital.ofdm_rx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
            self.unpack = blocks.packed_to_unpacked_bb(1, gr.GR_MSB_FIRST)

        self.rx_filter = filter.fir_filter_ccf(1, filter.firdes.low_pass(1.0, self.samp_rate, 100e3, 50e3))
        self.hop_ctrl = tod_hop_generator(key=bytes.fromhex(h_cfg.get('aes_key', '00'*32)), num_channels=h_cfg.get('num_channels', 50), center_freq=self.center_freq, channel_spacing=h_cfg.get('channel_spacing', 150000), dwell_ms=h_cfg.get('dwell_time_ms', 500))

    def connect_logic(self, mod_type, h_cfg):
        self.diag_proxy = MessageProxy(self.diag_ui_sig)
        self.status_proxy = MessageProxy(self.status_ui_sig)
        self.data_proxy = MessageProxy(self.data_ui_sig)

        self.msg_connect((self.mac_strobe, "strobe"), (self.session, "heartbeat"))
        src_port = "out" if self.payload_type == 'chat' else "strobe"
        self.msg_connect((self.pdu_src, src_port), (self.session, "data_in"))
        self.msg_connect((self.session, "pkt_out"), (self.pkt_a, "in"))
        self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
        
        if mod_type == "OFDM":
            # OFDM handles its own scaling
            self.connect(self.p2s_a, self.mod_a, self.usrp_sink)
            self.connect(self.usrp_source, self.rx_filter, self.demod_b, self.unpack, self.depkt_b)
        else:
            # v15.8.17: Scale complex samples AFTER modulation.
            self.connect(self.p2s_a, self.mod_a, self.mult_len, self.usrp_sink)
            self.connect(self.usrp_source, self.rx_filter, self.demod_b, self.depkt_b)

        self.msg_connect((self.depkt_b, "out"), (self.session, "msg_in"))
        self.msg_connect((self.depkt_b, "diagnostics"), (self.diag_proxy, "msg"))
        self.msg_connect((self.session, "status_out"), (self.status_proxy, "msg"))
        self.msg_connect((self.session, "data_out"), (self.data_proxy, "msg"))

        fft_size = 1024; fps_delay = 0.06
        self.snk_waterfall = qtgui.waterfall_sink_c(fft_size, fft.window.WIN_BLACKMAN_HARRIS, self.center_freq, self.samp_rate, "Tactical Display", 1)
        self.snk_waterfall.set_update_time(fps_delay) 
        self.viz_panel.addWidget(sip.wrapinstance(self.snk_waterfall.qwidget(), Qt.QWidget))
        self.connect(self.usrp_source, self.snk_waterfall)

        class UHDHandler(gr.basic_block):
            def __init__(self, usrp_src, usrp_snk):
                gr.basic_block.__init__(self, "UHDHandler", None, None); self.src, self.snk = usrp_src, usrp_snk
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
                self.last_f = 0
            def handle(self, msg):
                try:
                    f = pmt.to_double(pmt.dict_ref(msg, pmt.intern("freq"), pmt.from_double(0)))
                    t = pmt.to_double(pmt.dict_ref(msg, pmt.intern("time"), pmt.from_double(0)))
                    if f > 0 and f != self.last_f:
                        if t > (time.time() + 0.010):
                            cmd_time = uhd.time_spec(t)
                            self.src.set_command_time(cmd_time, 0)
                            self.snk.set_command_time(cmd_time, 0)
                            self.src.set_center_freq(f, 0)
                            self.snk.set_center_freq(f, 0)
                            self.src.clear_command_time(0)
                            self.snk.clear_command_time(0)
                        else:
                            self.src.set_center_freq(f, 0)
                            self.snk.set_center_freq(f, 0)
                        self.last_f = f
                except: pass
            def work(self, i, o): return 0
        self.uhd_h = UHDHandler(self.usrp_source, self.usrp_sink)
        self.msg_connect((self.hop_ctrl, "freq"), (self.uhd_h, "msg"))
        self.timer = QTimer(); self.timer.timeout.connect(lambda: self.hop_ctrl.handle_trigger(pmt.PMT_T))
        if h_cfg.get('enabled', True): self.timer.start(h_cfg['dwell_time_ms'])

    @pyqtSlot(object)
    def on_status_msg(self, msg):
        try:
            s = pmt.to_python(pmt.dict_ref(msg, pmt.intern("state"), pmt.from_long(0)))
            self.status_label.setText(f"Status: {s}")
            self.status_label.setStyleSheet(f"color: {'green' if s == 'CONNECTED' else 'orange'}; font-weight: bold;")
        except: pass

    @pyqtSlot(object)
    def on_data_msg(self, msg):
        try:
            raw = bytes(pmt.u8vector_elements(pmt.cdr(msg))).decode('utf-8', errors='replace')
            if raw.startswith("BFT|"):
                parts = raw.split("|")
                if len(parts) >= 4:
                    row = int(parts[1]) % 5
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
            ok_pmt = pmt.dict_ref(msg, pmt.intern("crc_ok"), pmt.PMT_F)
            ok = pmt.is_true(ok_pmt) or (pmt.is_bool(ok_pmt) and pmt.to_bool(ok_pmt))
            self.conf_bar.setValue(int(conf))
            self.crc_led.setText(f"CRC: {'OK' if ok else 'FAIL'}")
            self.crc_led.setStyleSheet(f"color: {'green' if ok else 'red'}; font-weight: bold;")
            self.fec_count.setText(f"FEC Repairs: {repairs}")
            ts = time.strftime("%H:%M:%S")
            self.lqi_history_list.insertItem(0, f"[{ts}] LQI: {conf:.1f}% | Repairs: {repairs} | CRC: {'OK' if ok else 'FAIL'}")
            if self.lqi_history_list.count() > 50: self.lqi_history_list.takeItem(50)
        except: pass

    def send_chat(self):
        txt = self.chat_input.text()
        if txt:
            self.text_out.append(f"<b>[SENT]:</b> {txt}")
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
