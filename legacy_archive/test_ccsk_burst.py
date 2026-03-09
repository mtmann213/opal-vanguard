import yaml
from packetizer import packetizer

with open('mission_configs/level7_ofdm_master.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

# Mock msg to test packetizer output length
import pmt
msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(120, [0xAA]*120))

class MockPacketizer(packetizer):
    def __init__(self):
        super().__init__("mission_configs/level7_ofdm_master.yaml")
        self.output_len = 0
    def message_port_pub(self, port, msg):
        v = pmt.cdr(msg)
        if pmt.is_u8vector(v):
            self.output_len = pmt.length(v)
            print(f"Packetizer output size: {self.output_len} items")

p = MockPacketizer()
p.handle_msg(msg)
