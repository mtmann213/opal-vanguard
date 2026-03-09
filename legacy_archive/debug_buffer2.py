import numpy as np
from gnuradio import gr, blocks, digital, filter, uhd
import pmt
import time

class test_tb(gr.top_block):
    def __init__(self):
        super().__init__()
        samp_rate = 500000
        sps = 10
        burst_size = 54560
        
        self.src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(burst_size, [1]*burst_size)), 500)
        self.p2s = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        self.p2s.set_max_output_buffer(131072)
        
        constel = digital.constellation_bpsk().base()
        self.diff_enc = digital.diff_encoder_bb(2)
        self.mod_a = digital.chunks_to_symbols_bc(constel.points(), 1)
        
        rrc_taps = filter.firdes.root_raised_cosine(sps, sps, 1.0, 0.35, 11*sps)
        self.tx_filter = filter.interp_fir_filter_ccc(sps, rrc_taps)
        self.tx_filter.set_max_output_buffer(524288) # Huge buffer for interpolated stream
        
        self.mult_len = blocks.tagged_stream_multiply_length(gr.sizeof_gr_complex, "packet_len", sps)
        
        # We need a large buffer for a 54k item tagged stream
        self.copy_blk = blocks.copy(gr.sizeof_gr_complex)
        self.copy_blk.set_max_output_buffer(524288) 
        
        # Hardware
        args_str = "type=b200"
        self.usrp_sink = uhd.usrp_sink(args_str, uhd.stream_args(cpu_format="fc32", channels=[0]), "packet_len")
        self.usrp_sink.set_samp_rate(samp_rate)
        self.usrp_sink.set_center_freq(915e6, 0)
        
        self.msg_connect((self.src, "strobe"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.diff_enc, self.mod_a, self.tx_filter, self.mult_len, self.copy_blk, self.usrp_sink)

if __name__ == '__main__':
    tb = test_tb()
    tb.start()
    time.sleep(3)
    tb.stop()
    tb.wait()
    print("SUCCESS")
