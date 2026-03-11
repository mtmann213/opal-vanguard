#!/usr/bin/env python3
import sys, os
import numpy as np

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dsp_helper import MatrixInterleaver, Scrambler, NRZIEncoder, CCSKProcessor
from rs_helper import RS1511

print("--- Test DSP ---")
data = b"HELLO WORLD! 123"

# 1. Interleaver
inter = MatrixInterleaver(rows=16)
i_data = inter.interleave(data)
r_data = inter.deinterleave(i_data)
print(f"Interleaver Pass: {r_data[:len(data)] == data}")

# 2. Scrambler
scram1 = Scrambler()
s_data = scram1.process(data)
scram2 = Scrambler()
r_data2 = scram2.process(s_data)
print(f"Scrambler Pass: {r_data2 == data}")

# 3. FEC
rs = RS1511()
nibs = []
for b in data[:11]: nibs.extend([(b >> 4) & 0x0F, b & 0x0F])
all_e = rs.encode(nibs[:11]) + rs.encode(nibs[11:])
fec_payload = b''
for m in range(0, 30, 2):
    fec_payload += bytes([( ((all_e[m]&0x0F) << 4) | (all_e[m+1]&0x0F) )])

# Decode
nibs_dec = []
for b in fec_payload: nibs_dec.extend([(b >> 4) & 0x0F, b & 0x0F])
dec1, _ = rs.decode(nibs_dec[:15])
dec2, _ = rs.decode(nibs_dec[15:])
combined = dec1 + dec2
healed = b''
for m in range(0, 22, 2): healed += bytes([( (combined[m] << 4) | combined[m+1] )])

print(f"FEC Pass: {healed == data[:11]}")


