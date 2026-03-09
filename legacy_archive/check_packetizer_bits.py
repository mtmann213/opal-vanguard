import pmt, sys, os
sys.path.append(os.path.join(os.getcwd(), 'src'))
from packetizer import packetizer

pkt = packetizer("mission_configs/level1_soft_link.yaml")
msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(10, [0xAA]*10))

pkt_output = []
pkt.message_port_pub = lambda port, msg: pkt_output.append(msg)
pkt.handle_msg(msg)

packed_bytes = list(pmt.u8vector_elements(pmt.cdr(pkt_output[0])))
bits = []
for b in packed_bytes:
    for i in range(8): bits.append((b >> (7-i)) & 1)

# Search for syncword 0x3D4C5B6A
sync_hex = "3D4C5B6A"
sync_bits = [int(b) for b in "".join(f"{int(c, 16):04b}" for c in sync_hex)]

def find_sequence(bits, seq):
    for i in range(len(bits) - len(seq)):
        if bits[i:i+len(seq)] == seq:
            return i
    return -1

pos = find_sequence(bits, sync_bits)
print(f"Syncword position in packetizer output: {pos}")
print(f"Total bits in packetizer output: {len(bits)}")
