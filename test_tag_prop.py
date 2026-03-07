from gnuradio import gr, blocks, digital
import pmt

class tb(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self)
        self.src = blocks.vector_source_b([1]*100, False)
        self.src.add_item_tag(0, 0, pmt.intern("tx_sob"), pmt.PMT_T)
        self.src.add_item_tag(0, 99, pmt.intern("tx_eob"), pmt.PMT_T)
        
        self.mod = digital.gfsk_mod(8, 0.1, 0.35, False, False, False)
        self.snk = blocks.tag_debug(gr.sizeof_gr_complex*1, "MOD_OUT")
        
        self.connect(self.src, self.mod, self.snk)

if __name__ == '__main__':
    t = tb()
    t.start()
    import time
    time.sleep(1)
    t.stop()
    t.wait()
