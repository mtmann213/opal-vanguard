import numpy as np
from gnuradio import gr, blocks, digital
import pmt, time, sys, os
sys.path.append(os.path.join(os.getcwd(), 'src'))
from packetizer import packetizer

class test_tb(gr.top_block):
    def __init__(self):
        super().__init__()
        self.pkt = packetizer("mission_configs/level1_soft_link.yaml")
        self.p2s = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        sensitivity = (2.0 * np.pi * 125000) / 500000
        self.mod = digital.gfsk_mod(10, sensitivity, 0.35, False, False, False)
        self.demod = digital.gfsk_demod(10, 0.1, 0.5, 0.005, 0.0)
        self.snk = blocks.vector_sink_b()
        
        self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.mod, self.demod, self.snk)

if __name__ == '__main__':
    tb = test_tb()
    tb.start()
    msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(10, [0xAA]*10))
    tb.pkt.handle_msg(msg)
    time.sleep(1.5)
    tb.stop(); tb.wait()
    
    data = list(tb.snk.data())
    sync_hex = "3D4C5B6A"
    sync_bits = [int(b) for b in "".join(f"{int(c, 16):04b}" for c in sync_hex)]
    
    best_dist = 32
    best_pos = -1
    for i in range(len(data) - 32):
        chunk = data[i:i+32]
        dist = sum(1 for a, b in zip(chunk, sync_bits) if a != b)
        if dist < best_dist:
            best_dist = dist
            best_pos = i
            
    print(f"Best match distance: {best_dist} at {best_pos}")
    if best_pos != -1:
        print(f"Data at best match: {data[best_pos:best_pos+32]}")
        print(f"Expected          : {sync_bits}")
