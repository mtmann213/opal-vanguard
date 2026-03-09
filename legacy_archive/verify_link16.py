import numpy as np

samp_rate = 1000000.0  # 1 Msps (N150 limit)
sps = 10.0             # Samples per symbol
sf = 32                # CCSK chips per 5-bit symbol (effectively 6.4 chips/bit)
freq_dev = 25000.0     # 25 kHz deviation

# 1. Base Symbol Rate
# Note: In Link-16/CCSK, we pack 5 bits into 32 chips.
base_sym_rate = samp_rate / sps
print(f"Base Symbol Rate: {base_sym_rate/1000} ksps")

# 2. Chip Rate
# If we run modulation AT the samp_rate, the bandwidth is huge.
# We need to know the occupied bandwidth of the GFSK signal.
# Occupied BW is roughly 2 * (freq_dev + symbol_rate)
bw = 2 * (freq_dev + base_sym_rate)
print(f"Occupied Bandwidth: {bw/1000} kHz")

# 3. Channel Check
channel_spacing = 150000.0
print(f"Does it fit in 150kHz channel? {'YES' if bw <= channel_spacing else 'NO'}")

# 4. Hop-set Check
num_channels = 50
total_hop_bw = num_channels * channel_spacing
print(f"Total Hopping Bandwidth: {total_hop_bw/1e6} MHz")
print(f"Does hop-set fit in 1Msps window? {'YES' if total_hop_bw <= samp_rate else 'NO'}")

