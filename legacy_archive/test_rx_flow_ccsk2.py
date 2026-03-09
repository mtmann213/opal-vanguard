import numpy as np
from gnuradio import gr, blocks, digital, filter, channels, analog
import pmt
import time
import yaml
from packetizer import packetizer

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

class test_tb(gr.top_block):
    def __init__(self):
        super().__init__()
        samp_rate = 500000
        sps = 10
        
        self.src = blocks.vector_source_b(burst, False)
        
        # TX Path from transceiver
        constel = digital.constellation_bpsk().base()
        self.unpack_tx = blocks.unpack_k_bits_bb(8)
        self.mod_a = digital.chunks_to_symbols_bc(constel.points(), 1)
        
        # Channel (no filters, just ideal conditions to see if phase is inverted)
        self.chan = channels.channel_model(noise_voltage=0.0)
        
        # RX Path
        self.demod_b = digital.constellation_decoder_cb(constel)
        self.snk = blocks.vector_sink_b()
        
        self.connect(self.src, self.unpack_tx, self.mod_a, self.chan, self.demod_b, self.snk)

if __name__ == '__main__':
    tb = test_tb()
    tb.start()
    time.sleep(2)
    tb.stop()
    tb.wait()
    
    rx_data = tb.snk.data()
    print(f"TX Bits: {len(burst)*8}")
    print(f"RX Bits: {len(rx_data)}")
    
    tx_bits = []
    for b in burst:
        tx_bits.extend([(b >> (7-i)) & 1 for i in range(8)])
        
    match = sum(1 for a, b in zip(tx_bits, rx_data) if a == b)
    print(f"Ideal match rate: {match/len(tx_bits)*100:.2f}%")
