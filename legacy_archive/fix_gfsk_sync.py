import sys

with open('src/depacketizer.py', 'r') as f:
    code = f.read()

# We need to increase the syncword error tolerance for GFSK.
# The fuzzy search showed 2 bit errors on a perfect loopback.
# In a real radio environment, it needs to be 4.
old_logic = "if (buf32 ^ sync_val).bit_count() <= 2: self.is_inverted, match = False, True"
new_logic = "if (buf32 ^ sync_val).bit_count() <= 4: self.is_inverted, match = False, True"

code = code.replace(old_logic, new_logic)

old_logic2 = "elif (buf32 ^ (0xFFFFFFFF ^ sync_val)).bit_count() <= 2: self.is_inverted, match = True, True"
new_logic2 = "elif (buf32 ^ (0xFFFFFFFF ^ sync_val)).bit_count() <= 4: self.is_inverted, match = True, True"

code = code.replace(old_logic2, new_logic2)

with open('src/depacketizer.py', 'w') as f:
    f.write(code)
