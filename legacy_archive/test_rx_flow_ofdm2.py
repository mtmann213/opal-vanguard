import yaml
from gnuradio import gr, pmt
import time
from packetizer import packetizer

p = packetizer("mission_configs/level7_ofdm_master.yaml")
msg_str = "HEARTBEAT FROM ALPHA".encode()
msg_in = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(msg_str), list(msg_str)))

class MockPacketizer(packetizer):
    def __init__(self):
        super().__init__("mission_configs/level7_ofdm_master.yaml")
        self.output_msg = None
    def message_port_pub(self, port, msg):
        self.output_msg = msg

mp = MockPacketizer()
mp.handle_msg(msg_in)
burst = list(pmt.u8vector_elements(pmt.cdr(mp.output_msg)))
print("Packetizer output length:", len(burst), "bytes")
