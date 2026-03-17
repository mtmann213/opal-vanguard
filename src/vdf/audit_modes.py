
import h5py
import numpy as np
import sys

VDF_CLASSES = [
    '32PSK', '16APSK', '32QAM', 'FM', 'GMSK', '32APSK', 'OQPSK', '8ASK',
    'BPSK', '8PSK', 'AM-SSB-SC', '4ASK', '16PSK', '64APSK', '128QAM',
    '128APSK', 'AM-DSB-SC', 'AM-SSB-WC', '64QAM', 'QPSK', '256QAM',
    'AM-DSB-WC', 'OOK', '16QAM'
]

def audit_modes(path):
    with h5py.File(path, 'r') as f:
        Y = f['Y'][:]
        Z = f['Z'][:]
        
        print(f"--- Dataset Audit: {path} ---")
        print(f"Total Snapshots: {len(Y)}")
        
        # Check the "Starved 8" specifically
        starved = ['32PSK', 'GMSK', '8ASK', 'BPSK', '4ASK', '16PSK', '64QAM', 'AM-DSB-WC']
        
        for name in VDF_CLASSES:
            idx = VDF_CLASSES.index(name)
            mask = (Y[:, idx] == 1)
            class_z = Z[mask]
            
            if len(class_z) == 0:
                continue
                
            # Modes: (CFO, Jamming)
            # CFO is at Z[1], Jamming is at Z[4]
            # Get unique combinations in class_z
            modes = {}
            for row in class_z:
                # Use rounding to avoid precision issues with float keys
                cfo_val = int(round(row[1]))
                jam_val = bool(round(row[4]))
                mode_key = (cfo_val, jam_val)
                modes[mode_key] = modes.get(mode_key, 0) + 1
            
            status = "[PATCHING]" if name in starved else "[OK]"
            print(f"{status} {name.ljust(10)} | Total: {len(class_z)}")
            for m, count in sorted(modes.items()):
                cfo, jam = m
                state = "JAMMED" if jam else "CLEAN"
                print(f"   -> CFO {str(cfo).ljust(5)} | {state.ljust(6)} : {count} snapshots")

if __name__ == "__main__":
    path = "data/vdf_captures/VDF_INDUSTRIAL_TOTAL.h5"
    if len(sys.argv) > 1:
        path = sys.argv[1]
    audit_modes(path)
