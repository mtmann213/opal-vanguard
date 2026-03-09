import pmt
import struct
from src.packetizer import packetizer

pkt = packetizer()
msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(4, [1,2,3,4]))

class MockPort:
    def __init__(self):
        self.data = None
    def __call__(self, port, msg):
        self.data = bytes(pmt.u8vector_elements(pmt.cdr(msg)))

port = MockPort()
pkt.message_port_pub = port
pkt.handle_msg(msg)

bits = port.data
print(f"Total bits: {len(bits)}")
print(f"First 10 bits: {list(bits[:10])}")

sync_bits = [int(b) for b in format(0x3D4C5B6A, '032b')]
sync_seq = bytes(sync_bits)

if sync_seq in bits:
    idx = bits.index(sync_seq)
    print(f"Found Syncword at index {idx}!")
    print(f"Preamble length before sync: {idx}")
else:
    print("CRITICAL: Syncword not found in packetizer output!")

