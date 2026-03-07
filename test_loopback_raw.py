import pmt
import struct
from src.packetizer import packetizer
from src.depacketizer import depacketizer
from gnuradio import gr, blocks, pdu
import time

class tb(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self)
        self.pkt = packetizer()
        self.depkt = depacketizer()
        
        self.p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.depkt)
        
        self.debug = blocks.message_debug()
        self.msg_connect((self.depkt, "out"), (self.debug, "print"))

if __name__ == '__main__':
    t = tb()
    t.start()
    time.sleep(1)
    
    # Try sending raw payload
    msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(4, [1,2,3,4]))
    t.pkt.handle_msg(msg)
    time.sleep(1)
    
    t.stop()
    t.wait()
    print("Done")
