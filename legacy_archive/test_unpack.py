import numpy as np
from gnuradio import gr, blocks

class test_tb(gr.top_block):
    def __init__(self):
        super().__init__()
        self.src = blocks.vector_source_b([0b10000001, 0b11110000])
        self.unpack = blocks.unpack_k_bits_bb(8)
        self.snk = blocks.vector_sink_b()
        self.connect(self.src, self.unpack, self.snk)

if __name__ == '__main__':
    tb = test_tb()
    tb.run()
    print(list(tb.snk.data()))
