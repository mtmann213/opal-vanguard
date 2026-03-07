import pmt
import struct
from src.session_manager import session_manager
from src.packetizer import packetizer
from src.depacketizer import depacketizer
from gnuradio import gr, blocks, pdu
import time

class tb(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self)
        self.session_a = session_manager()
        self.session_b = session_manager()
        self.pkt_a = packetizer()
        self.pkt_b = packetizer()
        self.depkt_a = depacketizer()
        self.depkt_b = depacketizer()
        
        self.p2s_a = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        self.p2s_b = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        # A -> B
        self.msg_connect((self.session_a, "pkt_out"), (self.pkt_a, "in"))
        self.msg_connect((self.pkt_a, "out"), (self.p2s_a, "pdus"))
        self.connect(self.p2s_a, self.depkt_b)
        self.msg_connect((self.depkt_b, "out"), (self.session_b, "msg_in"))
        
        # B -> A
        self.msg_connect((self.session_b, "pkt_out"), (self.pkt_b, "in"))
        self.msg_connect((self.pkt_b, "out"), (self.p2s_b, "pdus"))
        self.connect(self.p2s_b, self.depkt_a)
        self.msg_connect((self.depkt_a, "out"), (self.session_a, "msg_in"))

        self.debug = blocks.message_debug()
        self.msg_connect((self.session_a, "data_out"), (self.debug, "print"))
        self.msg_connect((self.session_b, "data_out"), (self.debug, "print"))

if __name__ == '__main__':
    t = tb()
    t.start()
    time.sleep(1)
    
    msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(4, [1,2,3,4]))
    print("A sends trigger...")
    t.session_a.handle_tx_request(msg)
    time.sleep(1)
    
    print(f"State A: {t.session_a.state}")
    print(f"State B: {t.session_b.state}")
    
    t.stop()
    t.wait()
    print("Done")
