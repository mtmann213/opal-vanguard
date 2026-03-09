import numpy as np
from gnuradio import gr, blocks, digital, fft
import pmt

class test_tb(gr.top_block):
    def __init__(self):
        super().__init__()
        fft_len = 64
        cp_len = 16
        
        # 1. Sync block requires a preamble
        # Standard OFDM preamble is two identical symbols in time domain
        # digital.ofdm_tx generates this automatically if we use it.
        
        self.tx = digital.ofdm_tx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
        self.rx = digital.ofdm_rx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
        
        # Test: If we put copy blocks with HUGE buffers, does it stop the crash?
        self.copy1 = blocks.copy(gr.sizeof_gr_complex)
        self.copy1.set_max_output_buffer(131072)
        
        self.src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(120, [0xAA]*120)), 500)
        self.p2s = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        self.msg_connect((self.src, "strobe"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.tx, self.copy1, self.rx, blocks.null_sink(gr.sizeof_char))

if __name__ == '__main__':
    tb = test_tb()
    print("Testing Standard OFDM with Buffer Breaks...")
    try:
        tb.start()
        import time
        time.sleep(2)
        tb.stop()
        tb.wait()
        print("SUCCESS: Standard OFDM is stable with buffer breaks!")
    except Exception as e:
        print(f"FAILED: {e}")
