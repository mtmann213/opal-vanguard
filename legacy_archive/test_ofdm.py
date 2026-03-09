from gnuradio import gr, digital, blocks
import pmt

class my_tb(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self)
        self.tx = digital.ofdm_tx(
            fft_len=64, 
            cp_len=16, 
            packet_length_tag_key="packet_len"
        )
        self.rx = digital.ofdm_rx(
            fft_len=64,
            cp_len=16,
            packet_length_tag_key="packet_len"
        )
        self.src = blocks.vector_source_b([1, 2, 3, 4], True, 1)
        self.stc = blocks.stream_to_tagged_stream(gr.sizeof_char, 1, 4, "packet_len")
        self.connect(self.src, self.stc, self.tx, self.rx, blocks.null_sink(gr.sizeof_char))

tb = my_tb()
print("OFDM blocks initialized successfully")
