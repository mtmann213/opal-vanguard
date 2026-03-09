sync_hex = "3D4C5B6A"
sync_bits = [int(b) for b in "".join(f"{int(c, 16):04b}" for c in sync_hex)]

with open('captured_bits.bin', 'rb') as f:
    bits = list(f.read())

best_dist = 32
best_pos = -1

for i in range(len(bits) - 32):
    chunk = bits[i:i+32]
    dist = sum(1 for a, b in zip(chunk, sync_bits) if a != b)
    if dist < best_dist:
        best_dist = dist
        best_pos = i
    if dist == 0: break

print(f"Best match for NORMAL syncword: distance {best_dist} at position {best_pos}")

# Try inverted
best_dist_inv = 32
best_pos_inv = -1
sync_inv = [1 - b for b in sync_bits]
for i in range(len(bits) - 32):
    chunk = bits[i:i+32]
    dist = sum(1 for a, b in zip(chunk, sync_inv) if a != b)
    if dist < best_dist_inv:
        best_dist_inv = dist
        best_pos_inv = i
    if dist == 0: break

print(f"Best match for INVERTED syncword: distance {best_dist_inv} at position {best_pos_inv}")
