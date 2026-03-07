from gnuradio import gr, blocks, digital, pdu
import pmt
import numpy as np

class tb(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self)
        self.src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(10, [1]*10)), 100)
        self.p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        self.mod = digital.gfsk_mod(8, 0.1, 0.35, False, False, False)
        self.snk = blocks.null_sink(gr.sizeof_gr_complex)
        
        self.msg_connect((self.src, "strobe"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.mod, self.snk)

if __name__ == '__main__':
    t = tb()
    t.start()
    import time
    time.sleep(2)
    t.stop()
    t.wait()
