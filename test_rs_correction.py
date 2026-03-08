from src.rs_helper import RS3115
import numpy as np

rs = RS3115()
data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
encoded = rs.encode(data)
print(f"Encoded: {encoded}")

# Corrupt 1 symbol (brute force limit in current rs_helper)
corrupted = list(encoded)
corrupted[0] ^= 0x1F
decoded = rs.decode(corrupted)
print(f"Decoded: {decoded}")

if decoded == data:
    print("SUCCESS: RS(31,15) corrected 1 symbol.")
else:
    print("FAILURE: RS(31,15) failed.")
