#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Live HDF5 Telemetry Monitor

import h5py
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import sys
import os
import time

VDF_CLASSES = [
    '32PSK', '16APSK', '32QAM', 'FM', 'GMSK', '32APSK', 'OQPSK', '8ASK',
    'BPSK', '8PSK', 'AM-SSB-SC', '4ASK', '16PSK', '64APSK', '128QAM',
    '128APSK', 'AM-DSB-SC', 'AM-SSB-WC', '64QAM', 'QPSK', '256QAM',
    'AM-DSB-WC', 'OOK', '16QAM'
]

def monitor_file(path):
    print(f"[MONITOR] Booting Live Telemetry for {os.path.basename(path)}")
    if not os.path.exists(path):
        print(f"[MONITOR] Waiting for file to be created...")
        while not os.path.exists(path):
            time.sleep(1)

    # Initialize Dashboard Plot
    plt.style.use('dark_background')
    fig, (ax_const, ax_text) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor('#0a0a0c')
    
    # Constellation Setup
    ax_const.set_facecolor('#000000')
    scat = ax_const.scatter([], [], s=2, color='#00ffcc', alpha=0.6)
    ax_const.set_xlim([-1.1, 1.1])
    ax_const.set_ylim([-1.1, 1.1])
    ax_const.axhline(0, color='#333333', lw=1)
    ax_const.axvline(0, color='#333333', lw=1)
    ax_const.set_title("Live Hardware Constellation", color='#00ffcc')
    
    # Telemetry Text Setup
    ax_text.axis('off')
    info_text = ax_text.text(0.1, 0.5, "Waiting for data...", color='#e0e0e0', fontsize=14, family='monospace', verticalalignment='center')
    
    last_size = 0
    
    def update(frame):
        nonlocal last_size
        try:
            # swmr=True allows reading while the writer is writing!
            with h5py.File(path, 'r', swmr=True) as f:
                if 'X' not in f: return scat, info_text
                current_size = f['X'].shape[0]
                
                if current_size > 0:
                    idx = current_size - 1
                    snapshot = f['X'][idx, :, 0] + 1j * f['X'][idx, :, 1]
                    Z = f['Z'][idx]
                    Y = f['Y'][idx]
                    
                    # Update Plot
                    scat.set_offsets(np.c_[np.real(snapshot), np.imag(snapshot)])
                    
                    # Extract Metadata
                    mod_name = VDF_CLASSES[np.argmax(Y)]
                    cfo = Z[2]
                    jam = bool(Z[4])
                    gain = Z[7]
                    peak = np.max(np.abs(snapshot))
                    
                    status = "[ JAMMED ]" if jam else "[ CLEAN ]"
                    color = "#ff3333" if jam else "#00ffcc"
                    
                    info = (
                        f"--- MISSION TELEMETRY ---\n\n"
                        f"Dataset Size:    {current_size:,} Snapshots\n"
                        f"Current Target:  {mod_name}\n"
                        f"Hardware Gain:   {gain} dB\n"
                        f"Estimated CFO:   {cfo:.1f} Hz\n"
                        f"Environment:     {status}\n"
                        f"Peak Amplitude:  {peak:.4f}\n\n"
                        f"STATUS: {'✓ SAVED' if current_size > last_size else 'WAITING FOR BURST...'}"
                    )
                    
                    info_text.set_text(info)
                    if current_size > last_size:
                        ax_const.set_title(f"Target: {mod_name} | Gain: {gain}dB", color=color)
                        
                    last_size = current_size
                    
        except Exception as e:
            # Expected if file is temporarily locked during a flush
            pass
            
        return scat, info_text

    # Poll the file every 1000ms
    ani = animation.FuncAnimation(fig, update, interval=1000, cache_frame_data=False)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    target = "data/vdf_captures/BPSK_GOLDEN_AUDIT.h5"
    if len(sys.argv) > 1: target = sys.argv[1]
    monitor_file(target)
