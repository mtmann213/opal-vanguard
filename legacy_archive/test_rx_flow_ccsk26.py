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
# Our test is passing...
# Why is the real link failing?
