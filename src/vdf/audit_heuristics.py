#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - VDF DSP Heuristic Auditor (v1.4 TorchSig-Ready)

import h5py
import numpy as np
import sys
import os
import argparse

# Expanded 57-Class TorchSig Vocabulary
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

# Universal DSP categories
CONSTANT_ENV = ['bpsk', 'qpsk', '8psk', '16psk', '32psk', '64psk', '2fsk', '2gfsk', '2msk', '2gmsk', 'fm']
MULTI_LEVEL = ['16qam', '32qam', '64qam', '128qam', '256qam', 'apsk', 'ask', 'pam']
ZERO_CROSSING = ['ook', 'am_dsb_sc', 'sc']

def calculate_papr(samples):
    peak = np.max(np.abs(samples))**2
    mean = np.mean(np.abs(samples)**2)
    return 10 * np.log10(peak / (mean + 1e-12))

def audit_class(name, samples, is_torchsig=False):
    mags = np.abs(samples)
    papr = calculate_papr(samples)
    origin_dens = np.mean(mags < 0.1)
    
    issues = []
    lower_name = name.lower()
    
    if any(x in lower_name for x in MULTI_LEVEL):
        if papr < 2.0: issues.append(f"Low PAPR ({papr:.1f}dB) - Data looks compressed/flat.")
    
    if any(x in lower_name for x in CONSTANT_ENV):
        if papr > 6.0: issues.append(f"High PAPR ({papr:.1f}dB) - Data looks noisy/distorted.")

    if any(x in lower_name for x in ZERO_CROSSING):
        if origin_dens < 0.05: issues.append(f"No origin crossings found - Squelch missing.")

    status = "✓ PASS" if not issues else "X FAIL"
    print(f"{status} | {name.ljust(12)} | PAPR: {papr:4.1f} dB | Origin: {origin_dens:4.2f}")
    for i in issues: print(f"   -> {i}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--torchsig", action="store_true", help="Audit a TorchSig format file")
    args = parser.parse_args()

    print(f"\n OPAL VANGUARD // HEURISTIC AUDITOR v1.4 (TorchSig-Ready)\n{'='*70}")
    
    with h5py.File(args.path, 'r') as f:
        X = f['X'][:]
        Y = f['Y'][:]
        
        # Auto-detect shape
        # TorchSig: (N, 2, 1024), VDF: (N, 1024, 2)
        if X.shape[1] == 2 and X.shape[2] > 2:
            print("[INFO] TorchSig format detected (Channels-First). Transposing...")
            X = np.transpose(X, (0, 2, 1))
        
        classes = TORCHSIG_57 if args.torchsig else VDF_CLASSES
        
        for name in classes:
            try:
                class_idx = classes.index(name)
                # Handle one-hot vs integer labels
                if len(Y.shape) > 1:
                    mask = (Y[:, class_idx] == 1)
                else:
                    mask = (Y == class_idx)
                
                indices = np.where(mask)[0]
                if len(indices) == 0: continue
                
                idx = np.random.choice(indices)
                snapshot = X[idx, :, 0] + 1j * X[idx, :, 1]
                audit_class(name, snapshot, is_torchsig=args.torchsig)
            except Exception as e:
                print(f"[{name}] Audit skipped: {e}")

    print("\n" + "="*70 + "\n AUDIT COMPLETE.\n" + "="*70)

if __name__ == "__main__": main()
