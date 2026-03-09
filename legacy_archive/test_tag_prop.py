import numpy as np
from gnuradio import gr, blocks, digital
import pmt

class test_tb(gr.top_block):
    def __init__(self):
        super().__init__()
        self.src = blocks.vector_source_b([0, 1]*10)
        
        class AddTags(gr.sync_block):
            def __init__(self): gr.sync_block.__init__(self, "AddTags", [np.uint8], [np.uint8])
            def work(self, i, o):
                if self.nitems_written(0) == 0:
                    self.add_item_tag(0, self.nitems_written(0), pmt.intern("packet_len"), pmt.from_long(20))
                o[0][:] = i[0]
                return len(i[0])
                
        self.tagger = AddTags()
        self.scale = blocks.tagged_stream_multiply_length(gr.sizeof_char, "packet_len", 10)
        self.mod = digital.gfsk_mod(10, 0.35, 0.5)
        
        self.snk = blocks.tag_debug(gr.sizeof_gr_complex, "after_mod")
        
        self.connect(self.src, self.tagger, self.scale, self.mod, self.snk)

if __name__ == '__main__':
    tb = test_tb()
    tb.run()
