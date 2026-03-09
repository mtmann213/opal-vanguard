import numpy as np
from gnuradio import gr, blocks, digital, filter, channels, analog
import pmt
import time
import yaml
from packetizer import packetizer
from depacketizer import depacketizer

with open('mission_configs/level7_ofdm_master.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

# Mock packetizer to generate valid payload
class MockPacketizer(packetizer):
    def __init__(self):
        super().__init__("mission_configs/level7_ofdm_master.yaml")
        self.output_msg = None
    def message_port_pub(self, port, msg):
        self.output_msg = msg

p = MockPacketizer()
msg_in = pmt.cons(pmt.make_dict(), pmt.init_u8vector(10, [0xAA]*10))
p.handle_msg(msg_in)
burst = list(pmt.u8vector_elements(pmt.cdr(p.output_msg)))

class MockDepacketizer(depacketizer):
    def __init__(self):
        super().__init__("mission_configs/level7_ofdm_master.yaml", ignore_self=False)
        self.output_msg = None
    def message_port_pub(self, port, msg):
        if pmt.symbol_to_string(port) == "out":
            self.output_msg = msg
            print("DEPACKETIZER SUCCESS:", bytes(pmt.u8vector_elements(pmt.cdr(msg))))

class test_tb(gr.top_block):
    def __init__(self):
        super().__init__()
        samp_rate = 500000
        sps = 10
        
        # PDU source outputs a PDU, not a vector. We want to test the full chain.
        # But wait! If the chain uses pdu_to_tagged_stream...
        self.src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(burst), burst)), 500)
        self.p2s = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        # Test WITHOUT diff encoding, since depacketizer handles inversion
        constel = digital.constellation_bpsk().base()
        self.unpack_tx = blocks.unpack_k_bits_bb(8)
        self.mod_a = digital.chunks_to_symbols_bc(constel.points(), 1)
        
        # Channel
        self.chan = channels.channel_model(noise_voltage=0.0)
        
        self.demod_b = digital.constellation_decoder_cb(constel)
        
        # The unpack_k_bits block was NOT removed from the BPSK TX path, it is unpacking the packed bytes.
        # The receiver demod_b outputs bytes with value 0 or 1.
        # The depacketizer in OFDM mode receives bytes and assumes they are packed bytes!
        
        self.depkt = MockDepacketizer()
        self.null_snk = blocks.null_sink(gr.sizeof_char)
        
        self.msg_connect((self.src, "strobe"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.unpack_tx, self.mod_a, self.chan, self.demod_b, self.depkt, self.null_snk)

if __name__ == '__main__':
    tb = test_tb()
    tb.start()
    time.sleep(2)
    tb.stop()
    tb.wait()
