from gnuradio import gr, blocks, digital, pdu, uhd
import pmt
import time

class tb(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self)
        self.src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(100, [1]*100)), 500)
        self.p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        self.mod = digital.gfsk_mod(8, 0.1, 0.35, False, False, False)
        
        self.mult = blocks.tagged_stream_multiply_length(gr.sizeof_gr_complex*1, "packet_len", 8)
        self.snk = uhd.usrp_sink("type=b200", uhd.stream_args("fc32"), "packet_len")
        
        self.msg_connect((self.src, "strobe"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.mod, self.mult, self.snk)

if __name__ == '__main__':
    t = tb()
    t.start()
    time.sleep(2)
    t.stop()
    t.wait()
    print("Success!")
