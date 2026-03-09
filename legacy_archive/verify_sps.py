import numpy as np

samp_rate = 1000000.0  # 1 Msps
channel_spacing = 200000.0 # 200 kHz
sf = 31

# Max allowed SPS to fit inside 200kHz channel using GFSK
# bw = 2 * (freq_dev + baud_rate)
# let freq_dev = 50000
# let baud_rate = x
# 200000 = 2 * (50000 + x) -> x = 50000 bps
# Since x = chip_rate = base_baud * sf
# base_baud = 50000 / 31 = ~1612 bps
# SPS = samp_rate / base_baud = 1000000 / 1612 = ~620

print("To fit DSSS sf=31 in 200kHz, the max chip rate is 50kcps.")
print("This corresponds to a base baud rate of ~1.6kbps.")
print("With a 1 Msps sample rate, this requires an SPS of ~620.")

print("GNU Radio blocks like PFB Clock Sync (used in PSK) will CRASH with SPS > ~32.")
print("Therefore, we MUST use GFSK (which has a simpler demodulator) OR we must decouple.")

