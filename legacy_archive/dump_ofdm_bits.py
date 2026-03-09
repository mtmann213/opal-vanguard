import numpy as np
from gnuradio import gr, blocks, digital
import pmt, time, yaml, os, sys

sys.path.append(os.path.join(os.getcwd(), 'src'))
from packetizer import packetizer
from usrp_transceiver import FreqDiffMapper, FreqDiffDemapper

class test_tb(gr.top_block):
    def __init__(self, config):
        super().__init__()
        self.pkt = packetizer(config)
        self.p2s = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        self.unpack = blocks.unpack_k_bits_bb(8)
        self.diff_map = FreqDiffMapper()
        self.diff_demap = FreqDiffDemapper()
        self.snk = blocks.vector_sink_b()
        self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.unpack, self.diff_map, self.diff_demap, self.snk)

if __name__ == '__main__':
    tb = test_tb("mission_configs/level7_ofdm_master.yaml")
    tb.start()
    msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(10, [0xAA]*10))
    tb.pkt.handle_msg(msg)
    time.sleep(1)
    tb.stop(); tb.wait()
    bits = "".join(str(b) for b in tb.snk.data())
    print("RECOVERED BITSTREAM:")
    print(bits)
