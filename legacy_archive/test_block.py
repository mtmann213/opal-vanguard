import numpy as np
from gnuradio import gr, blocks, digital
import pmt, time

class test_tb(gr.top_block):
    def __init__(self):
        super().__init__()
        self.src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(100, [0xAA]*100)), 500)
        self.p2s = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        self.mult = blocks.tagged_stream_multiply_length(gr.sizeof_char, "packet_len", 10)
        self.mod = digital.gfsk_mod(10, 0.1, 0.35, False, False, False)
        
        # A tagged stream block to simulate USRP sink blocking
        self.tsb = blocks.tagged_stream_align(gr.sizeof_gr_complex, "packet_len")
        self.snk = blocks.vector_sink_c()
        
        self.msg_connect((self.src, "strobe"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.mult, self.mod, self.tsb, self.snk)

tb = test_tb()
tb.start()
time.sleep(1.5)
tb.stop(); tb.wait()
print("Received samples:", len(tb.snk.data()))
