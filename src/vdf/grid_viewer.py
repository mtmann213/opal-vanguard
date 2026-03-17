#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Snapshot Grid Viewer

import h5py
import numpy as np
import matplotlib.pyplot as plt
import sys
import os

def generate_grid(path, start_idx=0):
    if not os.path.exists(path):
        print(f"!! Error: File {path} not found.")
        return

    print(f"[GRID VIEWER] Opening {path}...")
    with h5py.File(path, 'r') as f:
        X = f['X'][:]
        Z = f['Z'][:]
        
        if len(X) == 0:
            print("!! Error: Dataset is empty.")
            return

        # Ensure we don't go out of bounds
        end_idx = min(start_idx + 25, len(X))
        actual_count = end_idx - start_idx
        
        fig, axes = plt.subplots(5, 5, figsize=(20, 20))
        fig.patch.set_facecolor('#111')
        fig.suptitle(f"Dataset Evolution (Indices {start_idx} to {end_idx-1})\nFile: {os.path.basename(path)}", color='white', fontsize=20)
        
        for i, ax in enumerate(axes.flatten()):
            if i >= actual_count:
                ax.axis('off')
                continue
                
            idx = start_idx + i
            snapshot = X[idx, :, 0] + 1j * X[idx, :, 1]
            cfo = Z[idx, 2]
            
            ax.scatter(np.real(snapshot), np.imag(snapshot), s=1, color='#00ffcc', alpha=0.5)
            ax.set_xlim([-1.1, 1.1])
            ax.set_ylim([-1.1, 1.1])
            ax.axhline(0, color='white', lw=0.3)
            ax.axvline(0, color='white', lw=0.3)
            ax.set_facecolor('black')
            ax.set_title(f"Idx: {idx} | CFO: {cfo:.0f}Hz", color='white', fontsize=12)
            ax.set_xticks([])
            ax.set_yticks([])
            
            # Subtle red border if it's mostly noise (peak < 0.2)
            if np.max(np.abs(snapshot)) < 0.2:
                for spine in ax.spines.values():
                    spine.set_edgecolor('#ff3333')
                    spine.set_linewidth(2)
            else:
                for spine in ax.spines.values():
                    spine.set_edgecolor('#333')

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        save_path = 'vdf_grid_view.png'
        plt.savefig(save_path, facecolor=fig.get_facecolor())
        print(f"[GRID VIEWER] Grid saved to {save_path}")

if __name__ == "__main__":
    file_path = "data/vdf_captures/BLOB_LOCK.h5"
    start = 50
    if len(sys.argv) > 1: file_path = sys.argv[1]
    if len(sys.argv) > 2: start = int(sys.argv[2])
    generate_grid(file_path, start)
