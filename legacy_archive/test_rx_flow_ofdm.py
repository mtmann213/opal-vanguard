import numpy as np
from gnuradio import gr, blocks, digital, filter, channels, analog
import pmt
import time
import yaml
from packetizer import packetizer
from depacketizer import depacketizer

with open('mission_configs/level7_ofdm_master.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

# Mock packetizer to generate valid payload
class MockPacketizer(packetizer):
    def __init__(self):
        super().__init__("mission_configs/level7_ofdm_master.yaml")
        self.output_msg = None
    def message_port_pub(self, port, msg):
        self.output_msg = msg

p = MockPacketizer()
# Test with HEARTBEAT from ALPHA
msg_str = "HEARTBEAT FROM ALPHA".encode()
msg_in = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(msg_str), list(msg_str)))
p.use_comsec = True
p.comsec_key = bytes.fromhex(cfg['link_layer']['comsec_key'])
p.handle_msg(msg_in)

# For OFDM, packetizer outputs packed bytes? 
# Wait, let's look at the packetizer code for OFDM.
print("Output is list?", isinstance(p.output_msg, pmt.pmt))
