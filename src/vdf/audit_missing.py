
import h5py
import numpy as np

VDF_CLASSES = [
    '32PSK', '16APSK', '32QAM', 'FM', 'GMSK', '32APSK', 'OQPSK', '8ASK',
    'BPSK', '8PSK', 'AM-SSB-SC', '4ASK', '16PSK', '64APSK', '128QAM',
    '128APSK', 'AM-DSB-SC', 'AM-SSB-WC', '64QAM', 'QPSK', '256QAM',
    'AM-DSB-WC', 'OOK', '16QAM'
]

def find_missing_modes(path):
    with h5py.File(path, 'r') as f:
        Y = f['Y'][:]
        Z = f['Z'][:]
        
        print(f"--- Deep Mode Audit: {path} ---")
        
        expected_cfos = [-5000, 0, 5000]
        expected_jams = [False, True]
        
        missing_count = 0
        total_modes = len(VDF_CLASSES) * len(expected_cfos) * len(expected_jams)
        
        for name in VDF_CLASSES:
            class_idx = VDF_CLASSES.index(name)
            class_mask = (Y[:, class_idx] == 1)
            class_z = Z[class_mask]
            
            for cfo in expected_cfos:
                for jam in expected_jams:
                    # CFO is Z[1], Jamming is Z[4]
                    # We use np.isclose for float comparison
                    mode_mask = np.isclose(class_z[:, 1], float(cfo)) & np.isclose(class_z[:, 4], float(jam))
                    count = np.sum(mode_mask)
                    
                    if count == 0:
                        state_str = "JAMMED" if jam else "CLEAN"
                        print(f"!! MISSING: {name.ljust(10)} | CFO {str(cfo).ljust(5)} | {state_str}")
                        missing_count += 1
        
        print(f"--- Audit Summary ---")
        print(f"Total Modes: {total_modes}")
        print(f"Missing Modes: {missing_count}")
        print(f"Coverage: {((total_modes - missing_count) / total_modes)*100:.1f}%")

if __name__ == "__main__":
    find_missing_modes("data/vdf_captures/VDF_INDUSTRIAL_TOTAL.h5")
