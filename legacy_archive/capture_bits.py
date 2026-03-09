import numpy as np
from gnuradio import gr, blocks, digital
import pmt, time, yaml, os, sys

sys.path.append(os.path.join(os.getcwd(), 'src'))
from packetizer import packetizer

class test_tb(gr.top_block):
    def __init__(self, config):
        super().__init__()
        self.pkt = packetizer(config)
        self.p2s = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        self.unpack = blocks.unpack_k_bits_bb(8)
        self.mod = digital.gfsk_mod(10, 0.35, 0.5)
        self.demod = digital.gfsk_demod(10, 0.35, 0.5, 1.0, 0.1)
        self.snk = blocks.vector_sink_b()
        
        self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.unpack, self.mod, self.demod, self.snk)

if __name__ == '__main__':
    tb = test_tb("mission_configs/level1_soft_link.yaml")
    tb.start()
    # Send a known pattern
    data = [0x55, 0x66, 0x77, 0x88] * 10
    msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(data), data))
    tb.pkt.handle_msg(msg)
    time.sleep(2)
    tb.stop(); tb.wait()
    
    bits = tb.snk.data()
    # Save to file for analysis
    with open('captured_bits.bin', 'wb') as f:
        f.write(bytes(bits))
    print(f"Captured {len(bits)} bits to captured_bits.bin")
