
import h5py
import numpy as np
import sys
import os

def convert_to_raw(hdf5_path, output_path):
    print(f"[CONVERTER] Opening {hdf5_path}...")
    with h5py.File(hdf5_path, 'r') as f:
        X = f['X'][:] # Shape (N, 1024, 2)
        
        # Interleave I and Q into a single flat array
        # Reshape to (N*1024, 2) then flatten
        raw_interleaved = X.reshape(-1, 2).astype(np.float32)
        
        print(f"[CONVERTER] Writing {len(raw_interleaved)} samples to {output_path}...")
        raw_interleaved.tofile(output_path)
        print(f"[CONVERTER] Done. Use 'inspectrum -f 500000 {output_path}' to view.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 hdf5_to_raw.py <input.h5> [output.raw]")
        sys.exit(1)
        
    h5_in = sys.argv[1]
    raw_out = sys.argv[2] if len(sys.argv) > 2 else h5_in.replace(".h5", ".raw")
    convert_to_raw(h5_in, raw_out)
