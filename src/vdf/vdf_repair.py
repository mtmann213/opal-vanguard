#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - VDF Surgical Repair Script (v1.1 The Stubborn 3)

import os
import sys
import numpy as np
import time
from gnuradio import gr
import pmt

# Add current dir to path for local imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from vdf_master import VDFMaster, VDFSequencer, MissionState, normalize_name

# The "Stubborn 3" outliers
MISSING_MODES = [
    ('128QAM', 5000, False),
    ('128APSK', 5000, False),
    ('AM-DSB-WC', 0, True)
]

def run_repair(output_path, count=1000):
    print(f"\n[REPAIR] --- TARGETING THE STUBBORN 3 ---")
    
    # Initialize Master
    tb = VDFMaster(tx_serial="3449AC1", rx_serial="3457464", adv_serial="3457480", output_path=output_path)
    tb.start()
    
    # Lower threshold even further for these specific outliers
    tb.cap_engine.trigger_threshold = 0.05
    tb.cap_engine.search_timeout = 40.0
    
    # Load jammer profile
    jammer_wf = np.load("data/vdf_mock/jam_awgn.npy")
    
    try:
        for i, (mod_name, cfo, jam_active) in enumerate(MISSING_MODES):
            state_str = "JAMMED" if jam_active else "CLEAN"
            print(f"\n[Final {i+1}/3] Target: {mod_name} | CFO: {cfo} Hz | {state_str}")
            
            safe_name = normalize_name(mod_name)
            path = f"data/vdf_mock/{safe_name}_pilot.npy"
            if not os.path.exists(path): continue
                
            raw_payload = np.load(path)
            if len(raw_payload) > 100000:
                raw_payload = raw_payload[-100000:]
            
            # Fresh 20ms Pilot
            t_p = np.arange(int(tb.samp_rate * 0.02)) / tb.samp_rate
            pilot = 1.0 * np.exp(1j * 2 * np.pi * 100e3 * t_p).astype(np.complex64)
            silence = np.zeros(10000, dtype=np.complex64) # Massive gap for settling
            
            t_d = np.arange(len(raw_payload)) / tb.samp_rate
            cfo_shift = np.exp(1j * 2 * np.pi * cfo * t_d).astype(np.complex64)
            shifted_payload = raw_payload * cfo_shift
            
            final_wf = np.concatenate([pilot, silence, shifted_payload])
            
            state = MissionState(mod_type=mod_name)
            state.cfo = float(cfo); state.jamming = jam_active
            
            # Burst Cycle
            time.sleep(2.0) # Extra long settling
            tb.arm_receiver(state.to_dict(count))
            time.sleep(1.0)
            
            if jam_active:
                tb.load_waveform(jammer_wf, is_adv=True)
                time.sleep(0.1)
                
            print(f"[REPAIR] Firing burst...")
            tb.load_waveform(final_wf)
            time.sleep(25.0) # Maximum patience
            print(f"✓ Cycle Finished.")
            
    except Exception as e:
        print(f"\n[REPAIR] FATAL ERROR: {e}")
    finally:
        tb.stop(); tb.wait()
        print("[REPAIR] Trinity Released.")

if __name__ == "__main__":
    path = "data/vdf_captures/VDF_INDUSTRIAL_TOTAL.h5"
    run_repair(path)
