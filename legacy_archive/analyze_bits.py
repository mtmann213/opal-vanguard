import struct

sync_hex = "3D4C5B6A"
sync_bits = [int(b) for b in "".join(f"{int(c, 16):04b}" for c in sync_hex)]

with open('captured_bits.bin', 'rb') as f:
    bits = list(f.read())

print(f"File size: {len(bits)} bits")

def find_sequence(bits, seq):
    for i in range(len(bits) - len(seq)):
        if bits[i:i+len(seq)] == seq:
            return i
    return -1

pos = find_sequence(bits, sync_bits)
if pos != -1:
    print(f"SUCCESS: Found syncword at bit position {pos}")
    # Extract the first byte of the payload (the next 8 bits)
    payload_bits = bits[pos + 32 : pos + 32 + 8]
    val = 0
    for b in payload_bits: val = (val << 1) | b
    print(f"First byte after syncword (raw): 0x{val:02X}")
    
    # Try 1-bit shift forward
    payload_bits = bits[pos + 33 : pos + 33 + 8]
    val = 0
    for b in payload_bits: val = (val << 1) | b
    print(f"First byte after syncword (+1 shift): 0x{val:02X}")
else:
    print("FAIL: Syncword not found in bitstream")
