import numpy as np

samp_rate = 5000000.0
sps = 50.0
freq_dev = 50000.0
channel_spacing = 200000.0
num_channels = 20

# DSSS parameters
sf = 31

# 1. Base Baud Rate (before spreading)
base_baud_rate = samp_rate / sps
print(f"Base Baud Rate: {base_baud_rate/1000} kbps")

# 2. DSSS Chip Rate (actual over-the-air baud rate)
chip_rate = base_baud_rate * sf
print(f"DSSS Chip Rate: {chip_rate/1000} kcps")

# 3. Carson's Rule for GFSK Bandwidth (using chip rate!)
bw = 2 * (freq_dev + chip_rate)
print(f"DSSS GFSK Carson Bandwidth: {bw/1000} kHz")

# 4. Fit Check
print(f"Does signal fit in channel? {'YES' if bw < channel_spacing else 'NO'}")
print(f"Does hop-set fit in sample rate? {'YES' if (num_channels * channel_spacing) <= samp_rate else 'NO'}")

