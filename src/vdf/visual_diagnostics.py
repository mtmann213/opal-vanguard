
import h5py
import numpy as np
import matplotlib.pyplot as plt
import sys
import os

def run_diagnostic(path, snapshot_idx=-1):
    if not os.path.exists(path):
        print(f"!! Error: File {path} not found.")
        return

    with h5py.File(path, 'r') as f:
        X = f['X'][:]
        Y = f['Y'][:]
        Z = f['Z'][:]
        
        if len(X) == 0:
            print("!! Error: Dataset is empty.")
            return

        # Ensure index is valid
        if snapshot_idx >= len(X):
            snapshot_idx = len(X) - 1
            
        snapshot = X[snapshot_idx, :, 0] + 1j * X[snapshot_idx, :, 1]
        
        # Metadata Extraction
        # Z: [SNR, Intentional_CFO, Measured_HW_CFO, SPS, Jam_Active, Env_ID, Jam_Type, Gain]
        intentional_cfo = Z[snapshot_idx, 1]
        measured_hw_cfo = Z[snapshot_idx, 2]
        gain = Z[snapshot_idx, 7]
        jammed = bool(Z[snapshot_idx, 4])
        
        # Find Modulation Name
        VDF_CLASSES = [
            '32PSK', '16APSK', '32QAM', 'FM', 'GMSK', '32APSK', 'OQPSK', '8ASK',
            'BPSK', '8PSK', 'AM-SSB-SC', '4ASK', '16PSK', '64APSK', '128QAM',
            '128APSK', 'AM-DSB-SC', 'AM-SSB-WC', '64QAM', 'QPSK', '256QAM',
            'AM-DSB-WC', 'OOK', '16QAM'
        ]
        class_idx = np.argmax(Y[snapshot_idx])
        mod_name = VDF_CLASSES[class_idx]

        print(f"--- Diagnostic: {mod_name} (Index {snapshot_idx}) ---")
        print(f"Path:           {path}")
        print(f"Gain:           {gain} dB")
        print(f"Intentional CFO: {intentional_cfo} Hz")
        print(f"Measured HW CFO: {measured_hw_cfo:.2f} Hz (CORRECTED)")
        print(f"Status:         {'[JAMMED]' if jammed else '[CLEAN]'}")
        print(f"Peak Amplitude: {np.max(np.abs(snapshot)):.4f}")

        # Plotting
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))
        
        # 1. Constellation
        ax1.scatter(np.real(snapshot), np.imag(snapshot), s=2, color='#00ffcc', alpha=0.6)
        ax1.set_title(f"Constellation: {mod_name}\n(HW CFO Corrected)")
        ax1.set_xlim([-1.1, 1.1]); ax1.set_ylim([-1.1, 1.1])
        ax1.axhline(0, color='white', lw=0.5); ax1.axvline(0, color='white', lw=0.5)
        ax1.set_facecolor('black')
        
        # 2. Time Domain (Phase)
        ax2.plot(np.unwrap(np.angle(snapshot)), color='#ffcc00', lw=1)
        ax2.set_title("Unwrapped Phase (Time Domain)")
        ax2.set_ylabel("Radians")
        ax2.set_xlabel("Sample Index")
        ax2.set_facecolor('#111')
        ax2.grid(color='#333', alpha=0.5)

        plt.tight_layout()
        save_path = f"vdf_check_{mod_name.lower()}.png"
        plt.savefig(save_path)
        print(f"[DIAGNOSTIC] Visual saved to {save_path}")

if __name__ == "__main__":
    file_path = "data/vdf_captures/SPECTER_DESPINNED.h5"
    idx = -1
    if len(sys.argv) > 1: file_path = sys.argv[1]
    if len(sys.argv) > 2: idx = int(sys.argv[2])
    run_diagnostic(file_path, idx)
