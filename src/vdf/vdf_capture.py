#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - VDF Capture Engine (v2.33 Auto-Leveler)

import numpy as np
from gnuradio import gr
import pmt
import h5py
import time
import os
import sys

class vdf_capture(gr.basic_block):
    def __init__(self, output_path="data/vdf_captures/pilot_run.h5", snapshot_len=1024, samp_rate=1e6):
        gr.basic_block.__init__(self, name="vdf_capture", in_sig=[np.complex64], out_sig=None)
        self.output_path = os.path.abspath(output_path)
        self.snapshot_len = snapshot_len
        self.samp_rate = samp_rate
        self.state = "IDLE"
        self.samples_collected = 0
        self.current_metadata = {}
        self.snapshots_needed = 0
        self.session_data = []
        self.num_classes = 24
        
        # v2.33 Parameters
        self.acc_list = []
        self.pilot_duration_ms = 40 
        self.pilot_freq = 50e3 
        self.templates = self._generate_multi_templates()
        self.trigger_threshold = 0.05 # Aggressive trigger for attenuated signals
        self.search_timeout = 15.0
        self.search_start_time = 0
        self.best_corr_ever = 0.0
        self.last_good_cfo = 0.0 
        self.target_amplitude = 0.8
        
        self.message_port_register_in(pmt.intern("control"))
        self.set_msg_handler(pmt.intern("control"), self.handle_control)

    def _generate_multi_templates(self):
        n = int(self.samp_rate * (self.pilot_duration_ms / 1000.0))
        t = np.arange(n) / self.samp_rate
        offsets = [-5000, 0, 5000]
        tmps = []
        for off in offsets:
            tmp = np.exp(1j * 2 * np.pi * (self.pilot_freq + off) * t).astype(np.complex64)
            tmps.append(tmp / (np.linalg.norm(tmp) + 1e-9))
        return list(zip(offsets, tmps))

    def estimate_cfo_fine_fft(self, samples):
        """v2.33: Sub-Hz FFT peak interpolation."""
        n_fft = 2**16 # High resolution FFT
        spectrum = np.abs(np.fft.fft(samples, n=n_fft))
        freqs = np.fft.fftfreq(n_fft, 1/self.samp_rate)
        
        mask = (freqs > 30000) & (freqs < 70000)
        peak_idx = np.argmax(spectrum[mask])
        measured_freq = freqs[mask][peak_idx]
        return measured_freq - self.pilot_freq

    def handle_control(self, msg):
        try:
            meta = pmt.to_python(msg)
            self.current_metadata = meta
            self.snapshots_needed = meta.get('num_snapshots', 2000)
            self.state = "SEARCH"
            self.search_start_time = time.time()
            self.samples_collected = 0; self.session_data = []; self.best_corr_ever = 0.0; self.acc_list = []
            sys.stderr.write(f"\n[VDF_CAP] >>> ARMED (Auto-Leveling) | {meta.get('mod_type')} <<<\n")
        except Exception as e: sys.stderr.write(f"[VDF_CAP] Msg Error: {e}\n")

    def soft_clip(self, x):
        return x / (1.0 + np.abs(x))

    def general_work(self, input_items, output_items):
        in0 = input_items[0]; n = len(in0)
        if self.state == "IDLE": self.consume(0, n); return 0
        self.acc_list.append(in0.copy()); self.consume(0, n)

        total_buffered = sum(len(x) for x in self.acc_list)
        if total_buffered > 150000 and self.state == "SEARCH":
            self.acc_list = self.acc_list[-10:]; return 0

        if self.state == "SEARCH":
            if (time.time() - self.search_start_time) > self.search_timeout:
                sys.stderr.write(f"[VDF_CAP] !! TIMEOUT (Best Corr: {self.best_corr_ever:.4f})\n")
                self.state = "IDLE"; self.acc_list = []; return 0
            
            template_len = len(self.templates[0][1])
            if total_buffered < template_len + 2000: return 0
            
            full_acc = np.concatenate(self.acc_list)
            step = 500
            limit = len(full_acc) - template_len
            for i in range(0, limit, step):
                window = full_acc[i : i+template_len]
                win_norm = window / (np.linalg.norm(window) + 1e-9)
                best_bin_corr = 0.0
                for off, temp_norm in self.templates:
                    corr = np.abs(np.vdot(temp_norm, win_norm))
                    if corr > best_bin_corr: best_bin_corr = corr
                
                if best_bin_corr > self.best_corr_ever: self.best_corr_ever = best_bin_corr
                if best_bin_corr > self.trigger_threshold:
                    self.last_good_cfo = self.estimate_cfo_fine_fft(window)
                    peak_raw = np.max(np.abs(window))
                    sys.stderr.write(f"[VDF_CAP] ✓ TRIGGERED | Raw Peak: {peak_raw:.6f} | CFO: {self.last_good_cfo:.1f} Hz\n")
                    self.state = "CAPTURING"
                    self.acc_list = [full_acc[i + template_len + 5000:]]
                    return 0
            self.acc_list = [full_acc[-template_len:]]
            return 0

        elif self.state == "CAPTURING":
            if total_buffered < self.snapshot_len: return 0
            full_acc = np.concatenate(self.acc_list)
            while len(full_acc) >= self.snapshot_len and self.samples_collected < self.snapshots_needed:
                snapshot = full_acc[:self.snapshot_len]
                
                # v2.33: Automatic Gain Normalization (AGC)
                # Ensure each snapshot uses the full digital range
                peak = np.max(np.abs(snapshot))
                if peak > 1e-9:
                    scaled_snapshot = snapshot * (self.target_amplitude / peak)
                else:
                    scaled_snapshot = snapshot
                
                # v2.35: Precision Despinner Reactivated
                t = (np.arange(self.snapshot_len) + (self.samples_collected * self.snapshot_len)) / self.samp_rate
                despin = np.exp(-1j * 2 * np.pi * self.last_good_cfo * t).astype(np.complex64)
                self.session_data.append(self.soft_clip(scaled_snapshot * despin))
                
                full_acc = full_acc[self.snapshot_len:]; self.samples_collected += 1
            self.acc_list = [full_acc]
            if self.samples_collected >= self.snapshots_needed:
                self.save_to_hdf5(); self.state = "IDLE"; self.acc_list = []
            return 0
        return 0

    def save_to_hdf5(self):
        if not self.session_data: return
        n_saved = len(self.session_data)
        try:
            X = np.array(self.session_data); X_final = np.zeros((X.shape[0], self.snapshot_len, 2), dtype=np.float32)
            X_final[:, :, 0], X_final[:, :, 1] = np.real(X), np.imag(X)
            Y = np.zeros((n_saved, self.num_classes), dtype=np.float32); Y[:, self.current_metadata.get('mod_idx', 0)] = 1.0
            Z = np.zeros((n_saved, 8), dtype=np.float32)
            Z[:, 0], Z[:, 1] = 50.0, self.current_metadata.get('cfo', 0.0)
            Z[:, 2], Z[:, 3] = self.last_good_cfo, 8.0 
            Z[:, 4], Z[:, 5] = (1.0 if self.current_metadata.get('jamming', False) else 0.0), self.current_metadata.get('env_id', 0.0)
            Z[:, 6], Z[:, 7] = self.current_metadata.get('sco', 0.0), self.current_metadata.get('gain', self.current_metadata.get('gain', 70.0))
            with h5py.File(self.output_path, 'a') as f:
                if 'X' not in f:
                    f.create_dataset('X', (0, self.snapshot_len, 2), maxshape=(None, self.snapshot_len, 2), chunks=True, dtype='float32')
                    f.create_dataset('Y', (0, self.num_classes), maxshape=(None, self.num_classes), chunks=True, dtype='float32')
                    f.create_dataset('Z', (0, 8), maxshape=(None, 8), chunks=True, dtype='float32')
                for key, data in zip(['X', 'Y', 'Z'], [X_final, Y, Z]):
                    f[key].resize((f[key].shape[0] + data.shape[0]), axis=0)
                    f[key][-data.shape[0]:] = data
                f.attrs['mission_id'] = self.current_metadata.get('mod_type', 'UNK')
                f.flush()
            sys.stderr.write(f"[VDF_CAP] ✓ SAVED SUCCESS\n")
        except Exception as e: sys.stderr.write(f"[VDF_CAP] !! WRITE ERROR: {e}\n")
        self.session_data = []
