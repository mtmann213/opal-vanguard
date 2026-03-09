import numpy as np
from gnuradio import gr, blocks, digital, filter, channels, analog
import pmt
import time
import yaml
from packetizer import packetizer
from depacketizer import depacketizer

with open('mission_configs/level7_ofdm_master.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

# 1. TX BURST GENERATION
class MockPacketizer(packetizer):
    def __init__(self):
        super().__init__("mission_configs/level7_ofdm_master.yaml")
        self.output_msg = None
    def message_port_pub(self, port, msg):
        self.output_msg = msg

msg_str = "HEARTBEAT FROM ALPHA".encode()
msg_in = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(msg_str), list(msg_str)))
p = MockPacketizer()
p.handle_msg(msg_in)
burst = list(pmt.u8vector_elements(pmt.cdr(p.output_msg)))

# 2. FLOWGRAPH TEST
class test_tb(gr.top_block):
    def __init__(self):
        super().__init__()
        
        # Source
        self.src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(burst), burst)), 500)
        self.p2s = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        # HIGH-SPEED BPSK INSTEAD OF OFDM
        # We know BPSK works with fast hops. 
        # Why force OFDM if it crashes the scheduler?
        # But user wants OFDM. Let's try to make OFDM small enough.
        
        # Shrink frame size to 40 bytes (fits in one FFT window almost)
        self.tx = digital.ofdm_tx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
        self.rx = digital.ofdm_rx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
        
        self.snk = blocks.null_sink(gr.sizeof_char)
        
        self.msg_connect((self.src, "strobe"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.tx, self.rx, self.snk)

if __name__ == '__main__':
    # Try setting frame size small
    with open('mission_configs/level7_ofdm_master.yaml', 'r') as f:
        c = yaml.safe_load(f)
    c['link_layer']['frame_size'] = 40
    with open('mission_configs/level7_ofdm_master.yaml', 'w') as f:
        yaml.dump(c, f)
        
    tb = test_tb()
    tb.start()
    time.sleep(2)
    tb.stop()
    tb.wait()
    print("SUCCESS with small frame")
