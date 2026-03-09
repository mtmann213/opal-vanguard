import yaml
with open('mission_configs/level7_ofdm_master.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

hopping = cfg.get('hopping', {})
dwell = hopping.get('dwell_time_ms', 0)
print("Hopping Dwell Time:", dwell, "ms")

# Calculate burst duration
samp_rate = 500000
sps = 10

# Calculate exact number of bits for a 1024 byte packet with CCSK
# 1024 bytes = 8192 bits
# RS encoding expands this. (15,11) code expands it by roughly 15/11.
# Specifically, packetizer splits into 11-byte chunks.
# ceil(1024/11) = 94 chunks.
import math
chunks = math.ceil(1024 / 11)
rs_bytes = chunks * 15 # 94 * 15 = 1410 bytes
# Then it pads to 1024 target_bytes? Wait!
# Let's look at packetizer.py line 105:
# target_bytes = self.frame_size (1024)
# packet = data_to_transmit.ljust(target_bytes, b'\x00')[:target_bytes]
# This TRUNCATES the data! The RS data is 1410 bytes, but it's truncated to 1024 bytes.
# That breaks the CRC check and the RS decoding!
print("Wait! Is the packetizer truncating the RS encoded data?")
