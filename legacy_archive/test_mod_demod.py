import pmt
import struct
import numpy as np
from src.packetizer import packetizer
from src.depacketizer import depacketizer
from gnuradio import gr, blocks, pdu, digital, analog, filter
import time

class tb(gr.top_block):
    def __init__(self, sps, pre_len):
        gr.top_block.__init__(self)
        
        # We need a custom packetizer to inject the preamble
        class custom_packetizer(packetizer):
            def __init__(self, pre_len):
                super().__init__()
                self.pre_len = pre_len
            def handle_msg(self, msg):
                payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
                # Just mock the packetizer out_bits for this test
                preamble = [1,0]*self.pre_len
                syncword = [int(b) for b in format(0x3D4C5B6A, '032b')]
                
                # Mock final bits (just the payload bits)
                final_bits = []
                for b in payload: [final_bits.append((b >> (7-i)) & 1) for i in range(8)]
                
                out_bits = preamble + syncword + final_bits
                self.message_port_pub(pmt.intern("out"), pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(out_bits), out_bits)))

        self.pkt = custom_packetizer(pre_len)
        self.p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        # GFSK Mod/Demod
        samp_rate = 2e6
        sens = (2.0 * np.pi * 125000) / samp_rate
        self.mod = digital.gfsk_mod(sps, sens, 0.35, False, False, False)
        
        # Add some noise to simulate the channel
        self.noise = analog.noise_source_c(analog.GR_GAUSSIAN, 0.05)
        self.add = blocks.add_cc()
        
        self.demod = digital.gfsk_demod(sps, sens, 0.1, 0.5, 0.005, 0.0)
        
        # Custom depacketizer that just looks for syncword
        class custom_depacketizer(gr.sync_block):
            def __init__(self):
                gr.sync_block.__init__(self, name="custom_depacketizer", in_sig=[np.uint8], out_sig=None)
                self.bit_buf = 0
                self.found = False
            def work(self, input_items, output_items):
                in0 = input_items[0]
                for b in in0:
                    self.bit_buf = ((self.bit_buf << 1) | (int(b) & 1)) & 0xFFFFFFFF
                    if self.bit_buf == 0x3D4C5B6A and not self.found:
                        print("SYNCWORD FOUND BY DEMODULATOR!")
                        self.found = True
                return len(in0)
                
        self.depkt = custom_depacketizer()
        
        self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.mod, (self.add, 0))
        self.connect(self.noise, (self.add, 1))
        self.connect(self.add, self.demod, self.depkt)

if __name__ == '__main__':
    for pre in [16, 128, 1024]:
        print(f"\n--- Testing Modulation with Preamble Length {pre} ---")
        t = tb(8, pre)
        t.start()
        msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(4, [1,2,3,4]))
        t.pkt.handle_msg(msg)
        time.sleep(1)
        if not t.depkt.found: print("FAILED TO FIND SYNCWORD!")
        t.stop()
        t.wait()
