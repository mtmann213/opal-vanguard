#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - USRP B210/B205mini Transceiver (Definitive Baseline Build v7.3)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, analog, digital, qtgui, filter, fft, uhd, pdu
import pmt
import time
import struct
import socket
import threading
import base64
import json
from PyQt5 import Qt
from PyQt5.QtCore import pyqtSignal, QTimer
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
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from config_validator import validate_config

# ----------------------------------------------------------------------
# DASHBOARD EXTENSIONS: IQ & REMOTE CONTROL
# ----------------------------------------------------------------------
class IQDiagnosticProbe(gr.sync_block):
    def __init__(self, parent):
        gr.sync_block.__init__(self, name="IQProbe", in_sig=[np.complex64], out_sig=None)
        self.parent = parent; self.buffer = []; self.capturing = False
    def start_capture(self):
        if not self.capturing: self.buffer = []; self.capturing = True
    def work(self, input_items, output_items):
        if self.capturing:
            self.buffer.extend(input_items[0][:512])
            if len(self.buffer) >= 1024:
                self.capturing = False; self.parent.save_iq_snapshot(self.buffer[:1024])
        return len(input_items[0])

class RemoteControlListener(threading.Thread):
    def __init__(self, parent, port=9999):
        threading.Thread.__init__(self, daemon=True); self.parent = parent; self.port = port
    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(('127.0.0.1', self.port))
            while True:
                data, addr = sock.recvfrom(1024)
                cmd = json.loads(data.decode())
                if cmd['type'] == 'SET_GAIN':
                    Qt.QMetaObject.invokeMethod(self.parent.tx_gain_slider, "setValue", Qt.Qt.QueuedConnection, Qt.Q_ARG(int, int(cmd['tx'])))
                    Qt.QMetaObject.invokeMethod(self.parent.rx_gain_slider, "setValue", Qt.Qt.QueuedConnection, Qt.Q_ARG(int, int(cmd['rx'])))
                elif cmd['type'] == 'SET_CONFIG':
                    self.parent.reboot_signal.emit(cmd['config'])
        except: pass

class OpalVanguardUSRP(gr.top_block, Qt.QWidget):
    status_signal = pyqtSignal(str, str)
    data_signal = pyqtSignal(str)
    diag_signal = pyqtSignal(dict)
    reboot_signal = pyqtSignal(str)
    ghost_trigger_signal = pyqtSignal()

    def __init__(self, role="ALPHA", serial="", config_path="mission_configs/level1_soft_link.yaml"):
        gr.top_block.__init__(self, f"Opal Vanguard - {role}")
        Qt.QWidget.__init__(self)
        
        self.role = role; self.serial = serial; self.config_path = config_path
        self.reboot_requested = None
        
        success, msg = validate_config(config_path)
        if not success: print(f"FATAL CONFIG ERROR: {msg}"); sys.exit(1)
        
        self.setWindowTitle(f"Opal Vanguard Field Terminal - {role} [{serial}]")
        with open(config_path, 'r') as f: self.cfg = yaml.safe_load(f)
        print(f"--- [OPAL VANGUARD] {self.cfg['mission']['id']} ONLINE ---")
            
        hcfg = self.cfg['hopping']; hw_cfg = self.cfg['hardware']
        self.samp_rate = hw_cfg['samp_rate']; self.center_freq = self.cfg['physical']['center_freq']

        self.main_layout = Qt.QHBoxLayout(); self.setLayout(self.main_layout)
        self.ctrl_panel = Qt.QVBoxLayout(); self.main_layout.addLayout(self.ctrl_panel, 1)
        self.viz_panel = Qt.QVBoxLayout(); self.main_layout.addLayout(self.viz_panel, 3)
        
        self.ctrl_panel.addWidget(Qt.QLabel(f"<b>ROLE: {role}</b> | <b>SERIAL: {serial}</b>"))
        self.status_label = Qt.QLabel("Status: CONNECTED"); self.status_label.setStyleSheet("font-weight: bold; color: green;")
        self.ctrl_panel.addWidget(self.status_label)

        self.health_box = Qt.QGroupBox("Signal Health Monitor"); self.health_layout = Qt.QVBoxLayout(); self.health_box.setLayout(self.health_layout)
        self.conf_bar = Qt.QProgressBar(); self.conf_bar.setRange(0, 100); self.conf_bar.setValue(0); self.health_layout.addWidget(Qt.QLabel("Confidence:"))
        self.health_layout.addWidget(self.conf_bar); self.crc_led = Qt.QLabel("CRC: ---"); self.fec_count = Qt.QLabel("FEC Repairs: 0")
        self.blacklist_label = Qt.QLabel("AFH Blacklist: [DISABLED]"); self.blacklist_label.setStyleSheet("color: gray; font-weight: bold;")
        self.health_layout.addWidget(self.crc_led); self.health_layout.addWidget(self.fec_count); self.health_layout.addWidget(self.blacklist_label)
        self.ctrl_panel.addWidget(self.health_box)

        self.tx_gain_slider = Qt.QSlider(Qt.Qt.Horizontal); self.tx_gain_slider.setRange(0, 90); self.tx_gain_slider.setValue(hw_cfg['tx_gain'])
        self.rx_gain_slider = Qt.QSlider(Qt.Qt.Horizontal); self.rx_gain_slider.setRange(0, 90); self.rx_gain_slider.setValue(hw_cfg['rx_gain'])
        self.ctrl_panel.addWidget(Qt.QLabel("TX Gain")); self.ctrl_panel.addWidget(self.tx_gain_slider)
        self.ctrl_panel.addWidget(Qt.QLabel("RX Gain")); self.ctrl_panel.addWidget(self.rx_gain_slider)
        self.tx_gain_slider.valueChanged.connect(self.update_hardware); self.rx_gain_slider.valueChanged.connect(self.update_hardware)
        self.text_out = Qt.QTextEdit(); self.text_out.setReadOnly(True); self.ctrl_panel.addWidget(self.text_out)
        
        self.app_cfg = self.cfg.get('application_layer', {}); self.payload_type = self.app_cfg.get('payload_type', 'heartbeat')
        if self.payload_type == 'chat':
            self.chat_layout = Qt.QHBoxLayout(); self.chat_input = Qt.QLineEdit(); self.chat_btn = Qt.QPushButton("Send")
            self.chat_layout.addWidget(self.chat_input); self.chat_layout.addWidget(self.chat_btn); self.ctrl_panel.addLayout(self.chat_layout)
            class ChatSender(gr.basic_block):
                def __init__(self): gr.basic_block.__init__(self, "ChatSender", None, None); self.message_port_register_out(pmt.intern("out"))
                def send_msg(self, t): p = t.encode('utf-8'); self.message_port_pub(pmt.intern("out"), pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(p), list(p))))
                def work(self, i, o): return 0
            self.pdu_src = ChatSender(); self.chat_btn.clicked.connect(self.on_chat_send); self.chat_input.returnPressed.connect(self.on_chat_send)
        elif self.payload_type == 'file':
            self.file_layout = Qt.QHBoxLayout(); self.file_path_input = Qt.QLineEdit(); self.file_browse_btn = Qt.QPushButton("...")
            self.file_send_btn = Qt.QPushButton("Send File"); self.file_layout.addWidget(self.file_path_input); self.file_layout.addWidget(self.file_browse_btn); self.file_layout.addWidget(self.file_send_btn); self.ctrl_panel.addLayout(self.file_layout)
            self.file_progress = Qt.QProgressBar(); self.file_progress.setRange(0, 100); self.ctrl_panel.addWidget(self.file_progress)
            class FileSender(gr.basic_block):
                def __init__(self, parent):
                    gr.basic_block.__init__(self, "FileSender", None, None); self.parent = parent; self.message_port_register_out(pmt.intern("out")); self.fid = np.random.randint(0, 65535); self.sending = False
                def send_file(self, path):
                    if self.sending: return
                    self.sending = True; threading.Thread(target=self._thread, args=(path,), daemon=True).start()
                def _thread(self, path):
                    try:
                        with open(path, 'rb') as f: data = f.read()
                        chunks = [data[i:i+64] for i in range(0, len(data), 64)]
                        self.parent.data_signal.emit(f"<b>[TX FILE]:</b> {os.path.basename(path)} ({len(chunks)} chunks)")
                        for i, c in enumerate(chunks):
                            p = b'FTP!' + struct.pack('>HHH', self.fid, i, len(chunks)) + c
                            self.message_port_pub(pmt.intern("out"), pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(p), list(p))))
                            time.sleep(0.4)
                        self.parent.data_signal.emit(f"<b>[TX FILE]:</b> Complete")
                    except: pass
                    finally: self.sending = False
                def work(self, i, o): return 0
            self.pdu_src = FileSender(self); self.file_send_btn.clicked.connect(self.on_file_send); self.file_browse_btn.clicked.connect(self.on_file_browse)
        else:
            interval = 1000 if role == "ALPHA" else 1200
            self.pdu_src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(f"HEARTBEAT FROM {role}"), list(f"HEARTBEAT FROM {role}".encode()))), interval)

        # Hardware
        args_str = hw_cfg['args']
        if serial: args_str += f",serial={serial}"
        try:
            self.usrp_sink = uhd.usrp_sink(args_str, uhd.stream_args(cpu_format="fc32", channels=[0]))
            self.usrp_source = uhd.usrp_source(args_str, uhd.stream_args(cpu_format="fc32", channels=[0]))
            for dev in [self.usrp_sink, self.usrp_source]:
                dev.set_samp_rate(self.samp_rate); dev.set_center_freq(self.center_freq, 0)
            self.usrp_sink.set_gain(hw_cfg['tx_gain'], 0); self.usrp_sink.set_antenna(hw_cfg['tx_antenna'], 0)
            self.usrp_source.set_gain(hw_cfg['rx_gain'], 0); self.usrp_source.set_antenna(hw_cfg['rx_antenna'], 0)
            
            # Sync clock to System Time
            self.usrp_sink.set_time_now(uhd.time_spec(time.time()))
            print(f"[TERMINAL] USRP Clock Synced to: {time.ctime()}")
        except Exception as e: print(f"FATAL USRP: {e}"); sys.exit(1)

        sid = 1 if role == "ALPHA" else 2
        self.session = session_manager(initial_seed=hcfg.get('initial_seed', 0xACE), config_path=config_path)
        self.pkt_a = packetizer(config_path=config_path, src_id=sid); self.depkt_b = depacketizer(config_path=config_path, src_id=sid, ignore_self=True)
        
        # COMSEC Support
        if self.cfg['link_layer'].get('use_comsec', False):
            key = bytes.fromhex(self.cfg['link_layer'].get('comsec_key', '00'*32))
            self.pkt_a.use_comsec = True; self.pkt_a.aes_gcm = AESGCM(key)
            self.depkt_b.use_comsec = True; self.depkt_b.aes_gcm = AESGCM(key)
            print("[TERMINAL] COMSEC (AES-GCM) ENABLED")

        # 100% Continuous Architecture
        self.silence_src = analog.sig_source_b(self.samp_rate, analog.GR_CONST_WAVE, 0, 0, 0)
        self.pdu_in = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        self.add_stream = blocks.add_bb()
        
        mod_type = self.cfg['physical'].get('modulation', 'GFSK'); sps = self.cfg['physical'].get('samples_per_symbol', 8)
        self.mult_len = blocks.tagged_stream_multiply_length(gr.sizeof_gr_complex*1, "packet_len", sps)
        
        if mod_type in ["DBPSK", "DQPSK", "D8PSK"]:
            cp = 2 if "BPSK" in mod_type else (4 if "QPSK" in mod_type else 8)
            self.mod_a = digital.psk_mod(constellation_points=cp, mod_code=digital.mod_codes.GRAY_CODE, differential=True, samples_per_symbol=sps, excess_bw=0.35, verbose=False, log=False)
            self.demod_b = digital.psk_demod(constellation_points=cp, mod_code=digital.mod_codes.GRAY_CODE, differential=True, samples_per_symbol=sps, excess_bw=0.35, phase_bw=6.28/100, timing_bw=6.28/100, verbose=False, log=False)
        elif mod_type == "MSK": self.mod_a = digital.gmsk_mod(sps, 0.5); self.demod_b = digital.gmsk_demod(sps, 0.1, 0.5, 0.005, 0.0)
        elif mod_type == "OFDM": self.mod_a = digital.ofdm_tx(64, 16, "packet_len"); self.demod_b = digital.ofdm_rx(64, 16, "packet_len")
        else: self.mod_a = digital.gfsk_mod(sps, (2.0*np.pi*125000)/self.samp_rate, 0.35, False, False, False); self.demod_b = digital.gfsk_demod(sps, 0.1, 0.5, 0.005, 0.0)

        if hcfg.get('sync_mode') == "TOD": self.hop_ctrl = tod_hop_generator(bytes.fromhex(hcfg.get('aes_key', '00'*32)), hcfg.get('num_channels', 50), self.center_freq, hcfg.get('channel_spacing', 150000), hcfg.get('dwell_time_ms', 200), hcfg.get('lookahead_ms', 0))
        else: self.hop_ctrl = aes_hop_generator(bytes.fromhex(hcfg.get('aes_key', '00'*32)), hcfg.get('num_channels', 50), self.center_freq, hcfg.get('channel_spacing', 150000))
        
        self.rot_tx = blocks.rotator_cc(0); self.rot_rx = blocks.rotator_cc(0)
        self.rx_filter = filter.fir_filter_ccf(1, filter.firdes.low_pass(1.0, self.samp_rate, 100e3, 50e3)); self.iq_probe = IQDiagnosticProbe(self)

        # Connect
        src_port = "out" if self.payload_type in ['chat', 'file'] else "strobe"
        self.msg_connect((self.pdu_src, src_port), (self.session, "data_in")); self.msg_connect((self.session, "pkt_out"), (self.pkt_a, "in")); self.msg_connect((self.pkt_a, "out"), (self.pdu_in, "pdus"))
        
        self.connect(self.silence_src, (self.add_stream, 0))
        self.connect(self.pdu_in, (self.add_stream, 1))
        self.connect(self.add_stream, self.mod_a, self.mult_len, self.rot_tx, self.usrp_sink)
        
        self.connect(self.usrp_source, self.rx_filter, self.rot_rx, self.demod_b, self.depkt_b); self.connect(self.usrp_source, self.iq_probe)
        self.msg_connect((self.depkt_b, "out"), (self.session, "msg_in")); self.msg_connect((self.depkt_b, "diagnostics"), (self.session, "crc_fail")); self.msg_connect((self.session, "blacklist_out"), (self.hop_ctrl, "blacklist"))

        class UHDHandler(gr.basic_block):
            def __init__(self, parent):
                gr.basic_block.__init__(self, "UHDHandler", None, None); self.p = parent
                self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                try:
                    f = pmt.to_double(pmt.dict_ref(msg, pmt.intern("freq"), pmt.from_double(0))) if pmt.is_dict(msg) else pmt.to_double(msg)
                    if f > 0:
                        offset = f - self.p.center_freq
                        phase_inc = 2 * np.pi * offset / self.p.samp_rate
                        self.p.rot_tx.set_phase_inc(phase_inc)
                        self.p.rot_rx.set_phase_inc(-phase_inc)
                except: pass
            def work(self, i, o): return 0
        self.uhd_h = UHDHandler(self); self.msg_connect((self.hop_ctrl, "freq"), (self.uhd_h, "msg"))

        class DiagProxy(gr.basic_block):
            def __init__(self, parent): gr.basic_block.__init__(self, "DiagProxy", None, None); self.p = parent; self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                try:
                    d = {}; ok = pmt.to_bool(pmt.dict_ref(msg, pmt.intern("crc_ok"), pmt.from_bool(True))); d["crc_ok"] = ok
                    if not ok: self.p.iq_probe.start_capture()
                    d["confidence"] = pmt.to_double(pmt.dict_ref(msg, pmt.intern("confidence"), pmt.from_double(0))); d["fec_repairs"] = pmt.to_long(pmt.dict_ref(msg, pmt.intern("fec_repairs"), pmt.from_long(0)))
                    self.p.diag_signal.emit(d)
                except: pass
            def work(self, i, o): return 0
        self.dp = DiagProxy(self); self.msg_connect((self.depkt_b, "diagnostics"), (self.dp, "msg")); self.diag_signal.connect(self.on_diag); self.data_signal.connect(lambda p: self.text_out.append(p))

        class ConsoleDataLogger(gr.basic_block):
            def __init__(self, parent): gr.basic_block.__init__(self, "ConsoleLogger", None, None); self.p = parent; self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle); self.fbuf = {}
            def handle(self, msg):
                try:
                    p = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
                    if p.startswith(b'FTP!'):
                        fid, idx, tot = struct.unpack('>HHH', p[4:10]); dat = p[10:]; self.fbuf.setdefault(fid, {'c':{}, 't':tot})
                        if idx not in self.fbuf[fid]['c']:
                            self.fbuf[fid]['c'][idx] = dat
                            if hasattr(self.p, 'file_progress'): self.p.file_progress.setValue(int(len(self.fbuf[fid]['c'])/tot*100))
                            if len(self.fbuf[fid]['c']) == tot:
                                res = b''.join([self.fbuf[fid]['c'][i] for i in range(tot)])
                                with open(f"rx_{fid}.dat", 'wb') as f: f.write(res); self.p.data_signal.emit(f"<b>[RX]:</b> Saved rx_{fid}.dat"); del self.fbuf[fid]
                    else: text = p.decode('utf-8', 'ignore'); print(f"\033[94m[DATA RX]: {text}\033[0m"); self.p.data_signal.emit(f"<b>[RX]:</b> {text}")
                except: pass
            def work(self, i, o): return 0
        self.logger = ConsoleDataLogger(self); self.msg_connect((self.session, "data_out"), (self.logger, "msg"))

        self.ghost_mode = self.cfg['physical'].get('ghost_mode', False); self.ghost_timer = Qt.QTimer(); self.ghost_timer.setSingleShot(True); self.ghost_timer.timeout.connect(lambda: self.usrp_sink.set_gain(0, 0))
        self.ghost_trigger_signal.connect(self.start_ghost_tx)
        class GhostController(gr.basic_block):
            def __init__(self, parent): gr.basic_block.__init__(self, "GhostController", None, None); self.p = parent; self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                if self.p.ghost_mode: self.p.ghost_trigger_signal.emit()
            def work(self, i, o): return 0
        self.ghost_ctrl = GhostController(self); self.msg_connect((self.pkt_a, "out"), (self.ghost_ctrl, "msg"))

        class AMCHandler(gr.basic_block):
            def __init__(self, parent): gr.basic_block.__init__(self, "AMCHandler", None, None); self.p = parent; self.message_port_register_in(pmt.intern("msg")); self.set_msg_handler(pmt.intern("msg"), self.handle)
            def handle(self, msg):
                print("\033[93m[AMC] Link critical. Automatic reboot disabled for baseline stability.\033[0m")
            def work(self, i, o): return 0
        self.amc_h = AMCHandler(self); self.msg_connect((self.session, "amc_fallback"), (self.amc_h, "msg"))

        self.snk_waterfall = qtgui.waterfall_sink_c(2048, fft.window.WIN_BLACKMAN_HARRIS, self.center_freq, self.samp_rate, "Spectrum", 1)
        self.snk_waterfall.set_update_time(0.2)
        self.viz_panel.addWidget(sip.wrapinstance(self.snk_waterfall.qwidget(), Qt.QWidget)); self.connect(self.usrp_source, self.snk_waterfall)

        self.ctrl_listen = RemoteControlListener(self); self.ctrl_listen.start()
        self.timer = Qt.QTimer(); self.timer.timeout.connect(lambda: self.hop_ctrl.handle_trigger(pmt.PMT_T))
        if hcfg.get('enabled', True): self.timer.start(hcfg['dwell_time_ms'])
        self.reboot_signal.connect(self.execute_cold_reboot)

    def execute_cold_reboot(self, target_config):
        print(f"\033[41m*** EXECUTING COLD REBOOT TO {target_config} ***\033[0m")
        self.stop(); self.wait(); time.sleep(1.0)
        python = sys.executable; os.execv(python, [python, sys.argv[0], "--role", self.role, "--serial", self.serial, "--config", target_config])

    @Qt.pyqtSlot(float)
    def set_usrp_freq(self, f):
        try:
            self.usrp_sink.set_center_freq(f)
            self.usrp_source.set_center_freq(f)
        except: pass

    @Qt.pyqtSlot()
    def start_ghost_tx(self):
        if self.ghost_mode:
            self.usrp_sink.set_gain(self.tx_gain_slider.value(), 0)
            self.ghost_timer.start(150)

    def save_iq_snapshot(self, iq_buffer):
        try:
            flat = []; [flat.extend([float(c.real), float(c.imag)]) for c in iq_buffer]
            b64 = base64.b64encode(np.array(flat, dtype=np.float32).tobytes()).decode()
            with open("mission_telemetry.jsonl", "a") as f: f.write(json.dumps({"timestamp": time.time(), "event": "IQ_SNAPSHOT", "data": b64}) + "\n")
        except: pass

    def on_chat_send(self):
        t = self.chat_input.text()
        if t: self.text_out.append(f"<b>[TX]:</b> {t}"); self.pdu_src.send_msg(t); self.chat_input.clear()

    def on_file_send(self):
        p = self.file_path_input.text()
        if os.path.exists(p): self.pdu_src.send_file(p)

    def on_file_browse(self):
        fname, _ = Qt.QFileDialog.getOpenFileName(self, "Select File")
        if fname: self.file_path_input.setText(fname)

    def update_hardware(self):
        if not self.ghost_mode or self.ghost_timer.isActive(): self.usrp_sink.set_gain(self.tx_gain_slider.value(), 0)
        self.usrp_source.set_gain(self.rx_gain_slider.value(), 0)

    def on_diag(self, d):
        self.crc_led.setText(f"CRC: {'PASS' if d.get('crc_ok') else 'FAIL'} Bradley"); self.crc_led.setStyleSheet(f"color: {'green' if d.get('crc_ok') else 'red'};")
        self.conf_bar.setValue(int(d.get('confidence', 0))); self.fec_count.setText(f"FEC Repairs: {d.get('fec_repairs', 0)}")

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--role", default="ALPHA", choices=["ALPHA", "BRAVO"]); parser.add_argument("--serial", default=""); parser.add_argument("--config", default="mission_configs/level1_soft_link.yaml")
    args = parser.parse_args(); qapp = Qt.QApplication(sys.argv); tb = OpalVanguardUSRP(args.role, args.serial, args.config); tb.start(); tb.show(); qapp.exec_()

if __name__ == '__main__': main()
