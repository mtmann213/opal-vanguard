import numpy as np
from gnuradio import gr, blocks, digital
import pmt

class test_tb(gr.top_block):
    def __init__(self):
        super().__init__()
        self.src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(10, [0xAA]*10)), 1000)
        self.p2s = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        self.mod = digital.gfsk_mod(10, 0.1, 0.35, False, False, False)
        # CRITICAL: If the tag multiplier comes AFTER mod, does it work?
        self.mult = blocks.tagged_stream_multiply_length(gr.sizeof_gr_complex, "packet_len", 10)
        self.snk = blocks.tag_debug(gr.sizeof_gr_complex, "GFSK_OUT")
        self.connect(self.src, self.p2s, self.mod, self.mult, self.snk)

if __name__ == '__main__':
    tb = test_tb()
    tb.start()
    import time; time.sleep(1.5)
    tb.stop(); tb.wait()
