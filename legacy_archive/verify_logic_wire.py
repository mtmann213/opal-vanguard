import numpy as np
from gnuradio import gr, blocks, digital
import pmt, time, yaml, os, sys

sys.path.append(os.path.join(os.getcwd(), 'src'))
from packetizer import packetizer
from depacketizer import depacketizer

class test_tb(gr.top_block):
    def __init__(self, config):
        super().__init__()
        self.pkt = packetizer(config)
        self.depkt = depacketizer(config)
        self.p2s = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        sensitivity = (2.0 * np.pi * 25000) / 2000000
        self.mod = digital.gfsk_mod(10, sensitivity, 0.35, False, False, False)
        self.demod = digital.gfsk_demod(10, 0.1, 0.5, 0.005, 0.0)
        
        self.snk_demod = blocks.vector_sink_b()
        
        self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.mod, self.demod, self.depkt, blocks.null_sink(gr.sizeof_char))
        self.connect(self.demod, self.snk_demod)

        self.success = False
        def on_msg(msg):
            self.success = True
            print("DEPACKETIZER SUCCESS: MSG RECEIVED!")
        self.handler = gr.basic_block("handler", None, None)
        self.handler.message_port_register_in(pmt.intern("in"))
        self.handler.set_msg_handler(pmt.intern("in"), on_msg)
        self.msg_connect((self.depkt, "out"), (self.handler, "in"))

if __name__ == '__main__':
    tb = test_tb("mission_configs/level1_soft_link.yaml")
    tb.start()
    msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(10, [0xAA]*10))
    tb.pkt.handle_msg(msg)
    time.sleep(1.5)
    tb.stop(); tb.wait()
    
    if tb.success:
        print("TEST PASSED")
    else:
        print("TEST FAILED")
