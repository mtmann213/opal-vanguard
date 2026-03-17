
import h5py
import numpy as np
import matplotlib.pyplot as plt

def inspect_snapshots(path):
    with h5py.File(path, 'r') as f:
        X = f['X'][:]
        Y = f['Y'][:]
        Z = f['Z'][:]
        
        print(f"Dataset X Shape: {X.shape}")
        print(f"Dataset Z (Metadata) Sample (First 5):")
        print(Z[:5])
        
        # Find a BPSK (Class 0) and FM (Class 1) index
        bpsk_idx = np.where(Y[:, 0] == 1)[0][0]
        fm_idx = np.where(Y[:, 1] == 1)[0][0]
        
        # Plot BPSK
        plt.figure(figsize=(10, 8))
        plt.subplot(2, 1, 1)
        plt.plot(X[bpsk_idx, :, 0], label='I')
        plt.plot(X[bpsk_idx, :, 1], label='Q')
        plt.title(f"BPSK Snapshot (Index {bpsk_idx}) - Power: {np.mean(np.abs(X[bpsk_idx])**2):.6f}")
        plt.legend()
        
        # Plot FM
        plt.subplot(2, 1, 2)
        plt.plot(X[fm_idx, :, 0], label='I')
        plt.plot(X[fm_idx, :, 1], label='Q')
        plt.title(f"FM Snapshot (Index {fm_idx}) - Power: {np.mean(np.abs(X[fm_idx])**2):.6f}")
        plt.legend()
        
        plt.tight_layout()
        plt.savefig('vdf_snapshot_check.png')
        print("[INSPECTOR] Plot saved to vdf_snapshot_check.png")

        # Check for attributes
        print("--- HDF5 Attributes ---")
        for attr in f.attrs:
            print(f"{attr}: {f.attrs[attr]}")

if __name__ == '__main__':
    inspect_snapshots('data/vdf_captures/pilot_run.h5')
