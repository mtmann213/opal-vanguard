from gnuradio import gr, digital, blocks
import pmt
import numpy as np

class my_tb(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self)
        self.src = blocks.vector_source_b([1, 2, 3, 4], False)
        self.stc = blocks.stream_to_tagged_stream(gr.sizeof_char, 1, 4, "packet_len")
        self.tx = digital.ofdm_tx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
        self.sink = blocks.tag_debug(gr.sizeof_gr_complex, "OFDM_OUT")
        self.connect(self.src, self.stc, self.tx, self.sink)

tb = my_tb()
tb.run()
