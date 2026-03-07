import pmt
import struct
import random
import numpy as np
from src.packetizer import packetizer
from src.depacketizer import depacketizer
from gnuradio import gr, blocks, pdu
import time

class tb(gr.top_block):
    def __init__(self, noise_len):
        gr.top_block.__init__(self)
        self.pkt = packetizer()
        self.depkt = depacketizer()
        
        self.p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        # Add random noise before the packet
        noise_bits = [random.choice([0, 1]) for _ in range(noise_len)]
        
        class Injector(gr.sync_block):
            def __init__(self, noise):
                gr.sync_block.__init__(self, name="Injector", in_sig=[np.uint8], out_sig=[np.uint8])
                self.noise = noise
                self.injected = False
            def work(self, input_items, output_items):
                in0 = input_items[0]
                out = output_items[0]
                
                if not self.injected and len(in0) > 0:
                    req_len = len(self.noise) + len(in0)
                    if len(out) >= req_len:
                        out[:len(self.noise)] = self.noise
                        out[len(self.noise):req_len] = in0
                        self.injected = True
                        return req_len
                    else:
                        n = min(len(in0), len(out))
                        out[:n] = in0[:n]
                        return n
                else:
                    n = min(len(in0), len(out))
                    out[:n] = in0[:n]
                    return n
                    
        self.inj = Injector(noise_bits)
        
        self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.inj, self.depkt)
        
        self.debug = blocks.message_debug()
        self.msg_connect((self.depkt, "out"), (self.debug, "print"))

if __name__ == '__main__':
    for n_len in [0, 10, 100, 1000]:
        print(f"\n--- Testing with {n_len} noise bits ---")
        t = tb(n_len)
        t.start()
        msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(4, [1,2,3,4]))
        t.pkt.handle_msg(msg)
        time.sleep(0.5)
        t.stop()
        t.wait()
