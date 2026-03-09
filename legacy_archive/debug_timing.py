import yaml
with open('mission_configs/level7_ofdm_master.yaml', 'r') as f:
    cfg = yaml.safe_load(f)
    
hopping = cfg.get('hopping', {})
dwell = hopping.get('dwell_time_ms', 0)
print("Hopping Dwell Time:", dwell, "ms")

# Calculate burst duration
samp_rate = 500000
sps = 10
bits_per_burst = 54560
samples_per_burst = bits_per_burst * sps
burst_duration_ms = (samples_per_burst / samp_rate) * 1000

print(f"Burst duration: {burst_duration_ms} ms")
