import numpy as np
from gnuradio import gr, blocks, digital, fft
import pmt, time, yaml, os, sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))
from packetizer import packetizer
from depacketizer import depacketizer
from usrp_transceiver import FreqDiffMapper, FreqDiffDemapper, OFDMCarrierExtractor

class test_tb(gr.top_block):
    def __init__(self, config):
        super().__init__()
        self.pkt = packetizer(config)
        self.depkt = depacketizer(config)
        self.p2s = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        self.unpack = blocks.unpack_k_bits_bb(8)
        
        # Level 7 Logic (Simplified Wire Version)
        self.diff_map = FreqDiffMapper()
        self.diff_demap = FreqDiffDemapper()
        
        sync_hex = "3D4C5B6AACE12345"
        sync_bits = "".join(f"{int(c, 16):04b}" for c in sync_hex)
        self.corr = digital.correlate_access_code_tag_bb(sync_bits, 0, "sync_found")
        
        self.snk = blocks.null_sink(gr.sizeof_char)
        
        self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
        # WIRE TEST: Bits -> Diff Map -> Diff Demap -> Corr -> Depkt
        self.connect(self.p2s, self.unpack, self.diff_map, self.diff_demap, self.corr, self.depkt, self.snk)
        
        self.success = False
        def on_msg(msg): self.success = True
        self.handler = gr.basic_block("handler", None, None)
        self.handler.message_port_register_in(pmt.intern("in"))
        self.handler.set_msg_handler(pmt.intern("in"), lambda m: setattr(self, 'success', True))
        self.msg_connect((self.depkt, "out"), (self.handler, "in"))

if __name__ == '__main__':
    tb = test_tb("mission_configs/level7_ofdm_master.yaml")
    tb.start()
    msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(10, [0xAA]*10))
    tb.pkt.handle_msg(msg)
    time.sleep(1)
    tb.stop(); tb.wait()
    if tb.success: print("\033[92m[PASS]\033[0m Level 7 Logic Integrity Confirmed.")
    else: print("\033[91m[FAIL]\033[0m Level 7 logic is broken."); sys.exit(1)
