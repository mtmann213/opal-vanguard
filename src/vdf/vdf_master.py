#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - VDF Master Controller (v3.5 Final-Launcher)

import os
import sys
import numpy as np
from gnuradio import gr, blocks, uhd
import pmt
import time
import argparse
import h5py

# Add current dir to path for local imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from vdf_capture import vdf_capture
from vdf_vector_source import vdf_vector_source

# Canonical 24-Class List
VDF_CLASSES = [
    '32PSK', '16APSK', '32QAM', 'FM', 'GMSK', '32APSK', 'OQPSK', '8ASK',
    'BPSK', '8PSK', 'AM-SSB-SC', '4ASK', '16PSK', '64APSK', '128QAM',
    '128APSK', 'AM-DSB-SC', 'AM-SSB-WC', '64QAM', 'QPSK', '256QAM',
    'AM-DSB-WC', 'OOK', '16QAM'
]

def normalize_name(name):
    return name.lower().replace("-", "_")

class MissionLogger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a")
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()
    def flush(self):
        self.terminal.flush()
        self.log.flush()

class MissionState:
    def __init__(self, mod_type="BPSK"):
        self.mod_type = mod_type
        try:
            self.mod_idx = VDF_CLASSES.index(mod_type)
        except ValueError:
            self.mod_idx = 0
        self.snr, self.cfo, self.sco, self.sps = 50.0, 0.0, 0.0, 8.0
        self.jamming, self.alpha = False, 0.35

    def to_dict(self, num_snapshots=2000):
        return {
            'mod_type': self.mod_type, 'mod_idx': self.mod_idx,
            'num_snapshots': num_snapshots, 'snr': self.snr,
            'cfo': self.cfo, 'sco': self.sco, 'sps': self.sps,
            'jamming': self.jamming, 'alpha': self.alpha
        }

class VDFSequencer:
    def __init__(self, tb, snapshots_per_mod=1000, cfo_sweep=None, jam_sweep=False, single_mod=None):
        self.tb = tb
        self.snapshots_per_mod = snapshots_per_mod
        self.cfo_sweep = cfo_sweep if cfo_sweep else [0]
        self.jam_sweep = [False, True] if jam_sweep else [False]
        self.mods = [single_mod] if single_mod else VDF_CLASSES

    def run_sequence(self):
        print(f"\n[SEQUENCER] --- STARTING INDUSTRIAL HARVEST (v3.5) ---")
        
        jammer_wf = None
        if True in self.jam_sweep:
            jam_path = "data/vdf_mock/jam_awgn.npy"
            if os.path.exists(jam_path):
                jammer_wf = np.load(jam_path)

        for idx, mod_name in enumerate(self.mods):
            safe_name = normalize_name(mod_name)
            path = f"data/vdf_mock/{safe_name}_pilot.npy"
            if not os.path.exists(path): continue

            for cfo in self.cfo_sweep:
                for jam_active in self.jam_sweep:
                    try:
                        state_str = "JAMMED" if jam_active else "CLEAN"
                        print(f"\n[Mod {idx+1}/{len(self.mods)}] Target: {mod_name} | CFO: {cfo} Hz | {state_str}")
                        
                        raw_payload = np.load(path)
                        if len(raw_payload) > 100000:
                            raw_payload = raw_payload[-100000:]
                        
                        # Fresh 20ms Pilot (Zero-Drift)
                        t_p = np.arange(int(self.tb.samp_rate * 0.02)) / self.tb.samp_rate
                        pilot = 1.0 * np.exp(1j * 2 * np.pi * 100e3 * t_p).astype(np.complex64)
                        silence = np.zeros(5000, dtype=np.complex64)
                        
                        # Apply CFO ONLY to payload
                        t_d = np.arange(len(raw_payload)) / self.tb.samp_rate
                        cfo_shift = np.exp(1j * 2 * np.pi * cfo * t_d).astype(np.complex64)
                        shifted_payload = raw_payload * cfo_shift
                        
                        final_wf = np.concatenate([pilot, silence, shifted_payload])

                        state = MissionState(mod_type=mod_name)
                        state.cfo = float(cfo); state.jamming = jam_active
                        
                        time.sleep(1.0) 
                        self.tb.arm_receiver(state.to_dict(self.snapshots_per_mod))
                        time.sleep(0.5) 
                        
                        if jam_active and jammer_wf is not None:
                            self.tb.load_waveform(jammer_wf, is_adv=True)
                            time.sleep(0.1)

                        self.tb.load_waveform(final_wf)
                        time.sleep(18.0) # High-volume disk safety
                        print(f"✓ Burst Cycle Finished.")

                    except Exception as e:
                        print(f"!! ERROR: {e}")
                        time.sleep(5.0)
        
        print("\n[SEQUENCER] Harvest Complete.")

class VDFMaster(gr.top_block):
    def __init__(self, tx_serial, rx_serial, adv_serial, output_path, samp_rate=500e3):
        gr.top_block.__init__(self, "Vanguard Data Factory - Master")
        self.samp_rate = samp_rate
        self.usrp_tx = uhd.usrp_sink(f"serial={tx_serial}", uhd.stream_args(cpu_format="fc32", channels=[0]))
        self.usrp_rx = uhd.usrp_source(f"serial={rx_serial}", uhd.stream_args(cpu_format="fc32", channels=[0]))
        self.usrp_adv = uhd.usrp_sink(f"serial={adv_serial}", uhd.stream_args(cpu_format="fc32", channels=[0]))
        for dev in [self.usrp_tx, self.usrp_rx, self.usrp_adv]:
            dev.set_samp_rate(self.samp_rate)
            dev.set_center_freq(915e6, 0)
        self.usrp_rx.set_gain(90, 0); self.usrp_tx.set_gain(85, 0); self.usrp_adv.set_gain(70, 0)
        self.cap_engine = vdf_capture(output_path=output_path, samp_rate=self.samp_rate)
        self.tx_engine = vdf_vector_source(); self.adv_engine = vdf_vector_source()
        self.connect(self.tx_engine, self.usrp_tx); self.connect(self.usrp_rx, self.cap_engine); self.connect(self.adv_engine, self.usrp_adv)
    def load_waveform(self, samples, is_adv=False):
        (self.adv_engine if is_adv else self.tx_engine).to_basic_block().post(pmt.intern("control"), pmt.init_c32vector(len(samples), samples))
    def arm_receiver(self, metadata):
        self.cap_engine.to_basic_block().post(pmt.intern("control"), pmt.to_pmt(metadata))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tx", default="3449AC1"); parser.add_argument("--rx", default="3457464"); parser.add_argument("--adv", default="3457480")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--output", default="data/vdf_captures/VDF_INDUSTRIAL_TOTAL.h5")
    parser.add_argument("--cfo_sweep", type=str, default="0,5000,-5000")
    parser.add_argument("--jamming", action="store_true", default=True) # Default ON
    parser.add_argument("--mod", default=None)
    args = parser.parse_args()
    
    os.makedirs("data/vdf_captures", exist_ok=True)
    abs_output = os.path.abspath(args.output)
    log_name = abs_output.replace(".h5", ".log")
    sys.stdout = MissionLogger(log_name)
    
    print(f"\n--- [VDF INDUSTRIAL LOG START: {time.ctime()}] ---")
    print(f"[MASTER] Output Target: {abs_output}")
    tb = VDFMaster(args.tx, args.rx, args.adv, output_path=abs_output)
    tb.start()
    
    seq = VDFSequencer(tb, snapshots_per_mod=args.count, cfo_sweep=[int(x) for x in args.cfo_sweep.split(",")], jam_sweep=args.jamming, single_mod=args.mod)
    try:
        seq.run_sequence()
    except Exception as e: print(f"\n[VDF] FATAL: {e}")
    finally:
        tb.stop(); tb.wait()
        print("[VDF] Hardware Released.")

if __name__ == "__main__": main()
