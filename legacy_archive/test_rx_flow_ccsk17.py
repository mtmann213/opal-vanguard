import numpy as np
from gnuradio import gr, blocks, digital, filter, channels, analog
import pmt
import time
import yaml
from packetizer import packetizer

with open('mission_configs/level7_ofdm_master.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

class MockPacketizer(packetizer):
    def __init__(self):
        super().__init__("mission_configs/level7_ofdm_master.yaml")
        self.output_msg = None
    def message_port_pub(self, port, msg):
        self.output_msg = msg

p = MockPacketizer()
# Test with 1024 byte frame
msg_in = pmt.cons(pmt.make_dict(), pmt.init_u8vector(10, [0xAA]*10))
p.handle_msg(msg_in)
burst = list(pmt.u8vector_elements(pmt.cdr(p.output_msg)))
print(f"Packed Burst Size (bytes): {len(burst)}")
print(f"Unpacked Burst Size (bits): {len(burst)*8}")
print(f"Expected bits: 1024*8 = 8192")
print(f"Expected CCSK bits: 8192 * (32/5) = 52428.8. + preamble (1024) + sync (64) = 53516 bits.")
