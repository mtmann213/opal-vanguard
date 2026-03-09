import yaml
with open('mission_configs/level7_ofdm_master.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

hopping = cfg.get('hopping', {})
dwell = hopping.get('dwell_time_ms', 0)
print("Hopping Dwell Time:", dwell, "ms")

# Calculate burst duration AGAIN but carefully
samp_rate = 500000
sps = 10

frame_size = 1024
# Preamble 1024 bits
# Sync 64 bits
# Payload: 1024 bytes = 8192 bits
# Interleaved, scrambled, NRZI - doesn't change length
# CCSK: 8192 * (32/5) = 52428.8 bits -> 52429 bits
# Let's say ~53517 bits total.
# Pack to bytes: 6689 bytes.

# On TX side, we UNPACK these 6689 bytes. Wait.
# If we pack 53517 bits into bytes, it rounds up to 6690 bytes (53520 bits).
# Then unpack_k_bits_bb(8) produces 53520 bits.
# chunks_to_symbols produces 53520 complex samples.
# interpolating filter (sps=10) produces 535,200 complex samples!
# At 500,000 samples per second, 535,200 samples takes EXACTLY 1070.4 milliseconds to transmit.

# The session manager sends SYN pulses every 5 seconds if not connected.
# A hop occurs every 1500 ms.
# The USRP sink is continually tuning its center frequency based on UHDHandler.

# When the UHDHandler changes the frequency, does it flush the buffers?
# Yes! `set_center_freq` in UHD causes the LO to lock, which takes a few milliseconds,
# and it CAN interrupt an in-progress transmission!
print("Burst takes 1.07 seconds. Hop happens every 1.5 seconds.")
print("If the transmission starts 0.5s after a hop, it will be cut off by the next hop!")
