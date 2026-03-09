import numpy as np

samp_rate = 5000000.0  # 5 Msps

# The fundamental issue is that in GNU Radio, DSSS expands the number of symbols.
# We need to work backwards from the desired channel bandwidth.

desired_channel_bw = 200000.0 # 200 kHz
sf = 31

# For DBPSK, Null-to-Null bandwidth is ~ 2 * symbol_rate.
# To fit in 200kHz, symbol_rate (chip rate) must be < 100 kHz.
max_chip_rate = 100000.0 

# Base baud rate must then be:
base_baud_rate = max_chip_rate / sf
print(f"Required Base Baud Rate: {base_baud_rate} bps")

# In GNU Radio, baud_rate = samp_rate / sps.
# So required sps is:
required_sps = samp_rate / base_baud_rate
print(f"Required SPS for 5Msps: {required_sps}")

