
import h5py
import numpy as np
import matplotlib.pyplot as plt
import sys
import os

def run_power_diagnostic(path, snapshot_idx=-1):
    if not os.path.exists(path):
        print(f"!! Error: File {path} not found.")
        return

    with h5py.File(path, 'r') as f:
        X = f['X'][:]
        if len(X) == 0:
            print("!! Error: Dataset is empty.")
            return

        snapshot = X[snapshot_idx, :, 0] + 1j * X[snapshot_idx, :, 1]
        mags = np.abs(snapshot)
        phases = np.angle(snapshot)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        # Diagnostic 1: Power Histogram
        ax1.hist(mags, bins=100, color='#00ffcc', alpha=0.7, edgecolor='black')
        ax1.set_title("Signal vs. Noise Histogram")
        ax1.set_xlabel("Amplitude (Normalized)")
        ax1.set_ylabel("Sample Count")
        ax1.set_facecolor('#111')
        ax1.grid(color='#333', alpha=0.5)
        # Add interpretation text
        ax1.text(0.5, 0.9, "Hump at 0.5+ = SIGNAL\nPeak at 0.0 = NOISE", 
                 transform=ax1.transAxes, color='white', bbox=dict(facecolor='red', alpha=0.5))

        # Diagnostic 2: Phase Trajectory (is it spinning?)
        ax2.plot(phases[:200], color='#ffcc00', lw=1.5)
        ax2.set_title("Phase Trajectory (First 200 Samples)")
        ax2.set_xlabel("Sample Index")
        ax2.set_ylabel("Phase (Radians)")
        ax2.set_facecolor('#111')
        ax2.grid(color='#333', alpha=0.5)
        ax2.text(0.5, 0.9, "Diagonal Line = CFO Spinning\nJagged Jumps = NOISE", 
                 transform=ax2.transAxes, color='white', bbox=dict(facecolor='blue', alpha=0.5))

        plt.tight_layout()
        save_path = 'power_diagnostic.png'
        plt.savefig(save_path)
        print(f"[DIAGNOSTIC] Power analysis saved to {save_path}")
        
        # Calculate SNR Estimate (Peak-to-Floor)
        peak = np.max(mags)
        floor = np.mean(mags[:10]) # Rough noise floor
        print(f"--- Power Report ---")
        print(f"Peak Amplitude: {peak:.4f}")
        print(f"SNR Estimate:   {20*np.log10(peak/floor + 1e-9):.2f} dB")

if __name__ == "__main__":
    path = "data/vdf_captures/SPECTER_DESPINNED.h5"
    if len(sys.argv) > 1: path = sys.argv[1]
    run_power_diagnostic(path)
