#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Specter Sequencer (v1.6 Perfect-Test)

import os
import sys
import numpy as np
import time
import argparse
from gnuradio import gr, blocks, uhd
import pmt

# Imports from local VDF modules
vdf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vdf")
sys.path.append(vdf_dir)
from vdf_capture import vdf_capture
from vdf_vector_source import vdf_vector_source
from vdf_mock_gen import normalize_name, apply_sco_drift

VDF_CLASSES = [
    '32PSK', '16APSK', '32QAM', 'FM', 'GMSK', '32APSK', 'OQPSK', '8ASK',
    'BPSK', '8PSK', 'AM-SSB-SC', '4ASK', '16PSK', '64APSK', '128QAM',
    '128APSK', 'AM-DSB-SC', 'AM-SSB-WC', '64QAM', 'QPSK', '256QAM',
    'AM-DSB-WC', 'OOK', '16QAM'
]

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

class SpecterSequencer:
    def __init__(self, tb, snapshots_per_mode=1000):
        self.tb = tb
        self.snapshots = snapshots_per_mode
        self.env_id = 0
        self.gains = [40, 60, 80]
        self.scos = [-50, 0, 50]
        self.cfos = [-5000, 0, 5000]
        
    def run_harvest(self, single_mod=None):
        print(f"\n[SPECTER] --- STARTING MISSION: SPECTER'S EDGE (v1.7) ---")
        mods = [single_mod] if single_mod else VDF_CLASSES
        
        for mod_name in mods:
            safe_name = normalize_name(mod_name)
            path = f"data/vdf_mock/{safe_name}_pilot.npy"
            if not os.path.exists(path): continue
            
            raw_payload = np.load(path)
            # v1.7: Support new 1M sample payload length
            if len(raw_payload) > 1050000: raw_payload = raw_payload[-1050000:]
            
            for gain in self.gains:
                print(f"\n[SPECTER] Tuning Hardware Gain: {gain} dB")
                self.tb.usrp_tx.set_gain(gain, 0)
                time.sleep(1.0)
                
                for sco in self.scos:
                    jittered_payload = apply_sco_drift(raw_payload, ppm=sco)
                    for cfo in self.cfos:
                        print(f"   -> {mod_name} | Gain: {gain} | Testing Raw Signal Integrity...")
                        
                        t = np.arange(len(jittered_payload)) / self.tb.samp_rate
                        cfo_shift = np.exp(1j * 2 * np.pi * cfo * t).astype(np.complex64)
                        final_payload = jittered_payload * cfo_shift
                        
                        t_p = np.arange(int(self.tb.samp_rate * 0.04)) / self.tb.samp_rate
                        pilot = 1.0 * np.exp(1j * 2 * np.pi * 50e3 * t_p).astype(np.complex64)
                        silence = np.zeros(10000, dtype=np.complex64)
                        final_wf = np.concatenate([pilot, silence, final_payload])
                        
                        meta = {
                            'mod_type': mod_name, 'mod_idx': VDF_CLASSES.index(mod_name),
                            'num_snapshots': self.snapshots, 'gain': float(gain),
                            'sco': float(sco), 'cfo': float(cfo), 'env_id': float(self.env_id)
                        }
                        self.tb.arm_receiver(meta)
                        time.sleep(0.5)
                        self.tb.load_waveform(final_wf)
                        time.sleep(18.0) 
                        
        print("\n[SPECTER] Test Complete.")

class SpecterMaster(gr.top_block):
    def __init__(self, output_path, tx_serial="3449AC1", rx_serial="3457464", samp_rate=500e3):
        gr.top_block.__init__(self, "Specter Master")
        self.samp_rate = samp_rate
        self.usrp_tx = uhd.usrp_sink(f"serial={tx_serial}", uhd.stream_args(cpu_format="fc32", channels=[0]))
        self.usrp_rx = uhd.usrp_source(f"serial={rx_serial}", uhd.stream_args(cpu_format="fc32", channels=[0]))
        for dev in [self.usrp_tx, self.usrp_rx]:
            dev.set_samp_rate(self.samp_rate); dev.set_center_freq(915e6, 0)
            
        self.usrp_tx.set_antenna("TX/RX", 0)
        self.usrp_rx.set_antenna("TX/RX", 0)
        self.usrp_rx.set_gain(60, 0) # v1.7: Safe RX Gain
        
        self.cap_engine = vdf_capture(output_path=output_path, samp_rate=self.samp_rate)
        self.tx_engine = vdf_vector_source()
        self.connect(self.tx_engine, self.usrp_tx); self.connect(self.usrp_rx, self.cap_engine)
    def load_waveform(self, samples):
        self.tx_engine.to_basic_block().post(pmt.intern("control"), pmt.init_c32vector(len(samples), samples))
    def arm_receiver(self, metadata):
        self.cap_engine.to_basic_block().post(pmt.intern("control"), pmt.to_pmt(metadata))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mod", default=None)
    parser.add_argument("--env", type=int, default=0)
    parser.add_argument("--output", default="data/vdf_captures/VDF_SPECTER_ALPHA.h5")
    args = parser.parse_args()
    os.makedirs("data/vdf_captures", exist_ok=True)
    sys.stdout = MissionLogger(args.output.replace(".h5", ".log"))
    tb = SpecterMaster(output_path=args.output)
    tb.start()
    seq = SpecterSequencer(tb)
    seq.env_id = args.env
    try: seq.run_harvest(single_mod=args.mod)
    finally: tb.stop(); tb.wait(); print("[SPECTER] Hardware Released.")
