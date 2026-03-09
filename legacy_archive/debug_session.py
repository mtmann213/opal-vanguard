import yaml
with open('mission_configs/level7_ofdm_master.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

# Calculate exactly how many packets can be sent per dwell time
# Heartbeats are sent every 1000ms by the session_manager strobe
# Dwell time is 1500ms
# Burst duration is 1091ms
# There's a high chance the heartbeat triggers exactly when a hop is occurring,
# causing the burst to be cut off mid-air.

print("Burst duration:", 1091, "ms")
print("Dwell time:", 1500, "ms")
print("We need to check session_manager.py for heartbeat interval.")
