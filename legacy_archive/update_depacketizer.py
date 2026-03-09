import sys

with open('src/depacketizer.py', 'r') as f:
    code = f.read()

# Update scanning interval
old_interval = "if not found_now and (time.time() - self.last_sync_time) > 1.5:"
new_interval = "if not found_now and (time.time() - self.last_sync_time) > 0.1:"

code = code.replace(old_interval, new_interval)

with open('src/depacketizer.py', 'w') as f:
    f.write(code)
