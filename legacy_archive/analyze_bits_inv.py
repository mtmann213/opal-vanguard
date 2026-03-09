sync_hex = "3D4C5B6A"
sync_bits = [int(b) for b in "".join(f"{int(c, 16):04b}" for c in sync_hex)]
sync_inv = [1 - b for b in sync_bits]

with open('captured_bits.bin', 'rb') as f:
    bits = list(f.read())

def find_sequence(bits, seq):
    for i in range(len(bits) - len(seq)):
        if bits[i:i+len(seq)] == seq:
            return i
    return -1

pos = find_sequence(bits, sync_bits)
if pos != -1:
    print(f"SUCCESS: Found NORMAL syncword at bit position {pos}")
else:
    pos_inv = find_sequence(bits, sync_inv)
    if pos_inv != -1:
        print(f"SUCCESS: Found INVERTED syncword at bit position {pos_inv}")
    else:
        print("FAIL: Neither normal nor inverted syncword found.")
