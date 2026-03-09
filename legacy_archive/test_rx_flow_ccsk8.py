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
        
        self.src = blocks.vector_source_b(burst, False)
        
        # Test WITHOUT diff encoding, since depacketizer handles inversion
        constel = digital.constellation_bpsk().base()
        self.unpack_tx = blocks.unpack_k_bits_bb(8)
        self.mod_a = digital.chunks_to_symbols_bc(constel.points(), 1)
        
        # Channel
        self.chan = channels.channel_model(noise_voltage=0.0)
        
        self.demod_b = digital.constellation_decoder_cb(constel)
        self.depkt = MockDepacketizer()
        self.null_snk = blocks.null_sink(gr.sizeof_char)
        
        self.connect(self.src, self.unpack_tx, self.mod_a, self.chan, self.demod_b, self.depkt, self.null_snk)

if __name__ == '__main__':
    tb = test_tb()
    tb.start()
    time.sleep(2)
    tb.stop()
    tb.wait()
