#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - VDF Irrefutable Truth Auditor (v1.7 Universal-Truth)

import h5py
import numpy as np
import os
import sys
from scipy import signal

TORCHSIG_57 = [
    'ook', '4pam', '8pam', '16pam', '32pam', '64pam', '4ask', '8ask', '16ask', '32ask', '64ask',
    'bpsk', 'qpsk', '8psk', '16psk', '32psk', '64psk', '16qam', '32qam', '32qam_cross', '64qam',
    '128qam_cross', '256qam', '512qam_cross', '1024qam', '2fsk', '2gfsk', '2msk', '2gmsk',
    '4fsk', '4gfsk', '4msk', '4gmsk', '8fsk', '8gfsk', '8msk', '8gmsk', '16fsk', '16gfsk', '16msk',
    '16gmsk', '32fsk', '32gfsk', '32msk', '32gmsk', '64fsk', '64gfsk', '64msk', '64gmsk',
    'ofdm_64', 'ofdm_128', 'ofdm_256', 'ofdm_512', 'am_dsb', 'am_dsb_sc', 'am_lsb', 'am_usb'
]

VDF_CLASSES = [
    '32PSK', '16APSK', '32QAM', 'FM', 'GMSK', '32APSK', 'OQPSK', '8ASK',
    'BPSK', '8PSK', 'AM-SSB-SC', '4ASK', '16PSK', '64APSK', '128QAM',
    '128APSK', 'AM-DSB-SC', 'AM-SSB-WC', '64QAM', 'QPSK', '256QAM',
    'AM-DSB-WC', 'OOK', '16QAM'
]

def normalize_name(name):
    return name.lower().replace("-", "_")

def perform_single_audit(h5_path, mod_name, is_all=False):
    with h5py.File(h5_path, 'r') as f:
        X = f['X'][:]
        Y = f['Y'][:]
        
        # Auto-detect class list
        if Y.shape[1] == 57:
            classes = TORCHSIG_57
            is_torchsig = True
        else:
            classes = VDF_CLASSES
            is_torchsig = False
            
        if mod_name not in classes:
            return 0.0, "Invalid Class"
            
        class_idx = classes.index(mod_name)
        
        # Auto-detect transposition (TorchSig: N, 2, 1024)
        if X.shape[1] == 2: X = np.transpose(X, (0, 2, 1))
        
        # Handle one-hot vs integer labels
        if len(Y.shape) > 1:
            mask = (Y[:, class_idx] == 1)
        else:
            mask = (Y == class_idx)
            
        indices = np.where(mask)[0]
        if len(indices) == 0: return 0.0, "Empty"
        
        # Statistical Average: Test 3 random snapshots
        scores = []
        best_match = "None"
        num_tests = min(3, len(indices))
        test_indices = np.random.choice(indices, num_tests, replace=False)
        
        for t_idx in test_indices:
            harvest_snap = X[t_idx, :, 0] + 1j * X[t_idx, :, 1]
            
            # Optional CFO Correction (only if Z exists)
            correction = 1.0
            if 'Z' in f:
                Z = f['Z'][:]
                measured_cfo = Z[t_idx, 2]
                intentional_cfo = Z[t_idx, 1]
                t = np.arange(len(harvest_snap)) / 500000.0
                correction = np.exp(-1j * 2 * np.pi * (measured_cfo + intentional_cfo) * t).astype(np.complex64)
            
            harvest_snap_corrected = harvest_snap * correction
            
            local_best_score = 0.0
            local_best_name = "None"
            
            # Match search
            # In ALL mode, we verify the claimed label against its own mock
            search_list = [mod_name] if is_all else classes
            
            for class_name in search_list:
                safe_lookup = normalize_name(class_name)
                mock_path = f"data/vdf_mock/{safe_lookup}_pilot.npy"
                if not os.path.exists(mock_path): continue
                
                source_full = np.load(mock_path)
                source_payload = source_full[-1050000:] if len(source_full) > 1050000 else source_full
                
                # Complex Cross-Correlation
                target_src = source_payload[:100000]
                corr = signal.correlate(target_src, harvest_snap_corrected, mode='valid')
                
                norm = np.sqrt(np.sum(np.abs(target_src[:len(harvest_snap_corrected)])**2) * np.sum(np.abs(harvest_snap_corrected)**2))
                score = np.max(np.abs(corr)) / (norm + 1e-12)
                
                if score > local_best_score:
                    local_best_score = score
                    local_best_name = class_name
            
            scores.append(local_best_score)
            best_match = local_best_name
            
    avg_score = np.mean(scores)
    return avg_score, best_match

def run_irrefutable_audit(h5_path, mod_name):
    print(f"\n[TRUTH] --- COMMENCING UNIVERSAL TRUTH AUDIT ---")
    print(f"Targeting: {os.path.basename(h5_path)}")
    print(f"{'CLASS'.ljust(15)} | {'IDENTITY'.ljust(15)} | {'SCORE'.ljust(8)}")
    print("-" * 45)
    
    with h5py.File(h5_path, 'r') as f:
        Y = f['Y'][:]
        classes = TORCHSIG_57 if Y.shape[1] == 57 else VDF_CLASSES
        
    if mod_name == "ALL":
        for name in classes:
            score, identity = perform_single_audit(h5_path, name, is_all=True)
            if identity != "Empty":
                # Real-world threshold vs Simulated Threshold
                thresh = 0.35 if "SPECTER" in h5_path else 0.5
                marker = "✓" if score > thresh else "X"
                print(f"{marker} {name.ljust(13)} | {identity.ljust(15)} | {score:.4f}")
        return

    score, identity = perform_single_audit(h5_path, mod_name)
    thresh = 0.35 if "SPECTER" in h5_path else 0.5
    marker = "✓" if score > thresh else "X"
    print(f"{marker} {mod_name.ljust(13)} | {identity.ljust(15)} | {score:.4f}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 src/vdf/irrefutable_audit.py <PATH_TO_H5> <MOD_NAME>")
        sys.exit(1)
    run_irrefutable_audit(sys.argv[1], sys.argv[2])
