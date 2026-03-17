#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - VDF HDF5 Verifier (v1.0)

import h5py
import numpy as np
import sys

def verify(path):
    print(f"[VERIFIER] Opening {path}...")
    try:
        with h5py.File(path, 'r') as f:
            print(f"--- HDF5 Structure ---")
            for key in f.keys():
                print(f"Dataset: {key} | Shape: {f[key].shape} | Dtype: {f[key].dtype}")
            
            # Check for non-zero data in X
            X = f['X'][:]
            pwr = np.mean(np.abs(X)**2)
            print(f"--- Data Integrity ---")
            print(f"Mean Power in X: {pwr:.6f}")
            if pwr > 0:
                print("\033[92m[SUCCESS] High-fidelity data detected!\033[0m")
            else:
                print("\033[91m[FAILURE] Dataset contains only zeros.\033[0m")
                
            # Check Y labels
            Y = f['Y'][:]
            classes = np.sum(Y, axis=0)
            print(f"Class Distribution: {classes}")
            
    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")

if __name__ == "__main__":
    path = "data/vdf_captures/pilot_run.h5"
    if len(sys.argv) > 1:
        path = sys.argv[1]
    verify(path)
