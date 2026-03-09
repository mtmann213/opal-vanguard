import numpy as np
import yaml
from gnuradio import gr, blocks
import pmt
import time
from packetizer import packetizer
from depacketizer import depacketizer

with open('mission_configs/level7_ofdm_master.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

class MockPacketizer(packetizer):
    def __init__(self):
        super().__init__("mission_configs/level7_ofdm_master.yaml")
        self.output_msg = None
    def message_port_pub(self, port, msg):
        self.output_msg = msg

p = MockPacketizer()
msg_in = pmt.cons(pmt.make_dict(), pmt.init_u8vector(10, [0xAA]*10))
p.handle_msg(msg_in)
burst = list(pmt.u8vector_elements(pmt.cdr(p.output_msg)))

print(f"Generated {len(burst)} packed bytes")
bits = []
for b in burst:
    bits.extend([(b >> (7-i)) & 1 for i in range(8)])

print(f"Unpacked to {len(bits)} bits")

class MockDepacketizer(depacketizer):
    def __init__(self):
        super().__init__("mission_configs/level7_ofdm_master.yaml", ignore_self=False)
        self.output_msg = None
    def message_port_pub(self, port, msg):
        if pmt.symbol_to_string(port) == "out":
            self.output_msg = msg
            print("DEPACKETIZER SUCCESS:", bytes(pmt.u8vector_elements(pmt.cdr(msg))))
        elif pmt.symbol_to_string(port) == "diagnostics":
            print("DIAG:", msg)

class test_tb(gr.top_block):
    def __init__(self):
        super().__init__()
        
        # We pass bits directly into depacketizer
        self.src = blocks.vector_source_b(bits, False)
        self.depkt = MockDepacketizer()
        self.null_snk = blocks.null_sink(gr.sizeof_char)
        
        self.connect(self.src, self.depkt, self.null_snk)

if __name__ == '__main__':
    tb = test_tb()
    tb.start()
    time.sleep(2)
    tb.stop()
    tb.wait()
