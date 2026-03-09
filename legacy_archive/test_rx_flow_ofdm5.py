import numpy as np
from gnuradio import gr, blocks, digital, filter, channels, analog
import pmt
import time
import yaml
from packetizer import packetizer
from depacketizer import depacketizer

with open('mission_configs/level7_ofdm_master.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

# 1. TX BURST GENERATION
class MockPacketizer(packetizer):
    def __init__(self):
        super().__init__("mission_configs/level7_ofdm_master.yaml")
        self.output_msg = None
    def message_port_pub(self, port, msg):
        self.output_msg = msg

msg_str = "HEARTBEAT FROM ALPHA".encode()
msg_in = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(msg_str), list(msg_str)))
p = MockPacketizer()
p.use_comsec = True
p.comsec_key = bytes.fromhex(cfg['link_layer']['comsec_key'])
p.handle_msg(msg_in)
burst = list(pmt.u8vector_elements(pmt.cdr(p.output_msg)))

# 2. FLOWGRAPH TEST
class test_tb(gr.top_block):
    def __init__(self):
        super().__init__()
        
        # Source
        self.src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(burst), burst)), 500)
        self.p2s = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        # KEY CHANGE: Let's use simpler OFDM parameters
        # occupied_carriers must match between TX and RX!
        # Default is ([-26, -25, -24, -23, -22, -21, -20, -19, -18, -17, -16, -15, -14, -13, -12, -11, -10, -9, -8, -7, 
        #              -6, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 
        #              19, 20, 21, 22, 23, 24, 25, 26],)
        
        # OFDM TX
        self.tx = digital.ofdm_tx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
        
        # Channel
        self.chan = channels.channel_model(noise_voltage=0.0)
        
        # OFDM RX
        self.rx = digital.ofdm_rx(fft_len=64, cp_len=16, packet_length_tag_key="packet_len")
        
        # Depacketizer
        class MockDepacketizer(depacketizer):
            def __init__(self):
                super().__init__("mission_configs/level7_ofdm_master.yaml", ignore_self=False)
                self.success = False
            def message_port_pub(self, port, msg):
                if pmt.symbol_to_string(port) == "out":
                    print("SUCCESS:", bytes(pmt.u8vector_elements(pmt.cdr(msg))))
                    self.success = True
        
        self.depkt = MockDepacketizer()
        self.null_snk = blocks.null_sink(gr.sizeof_char)
        
        self.msg_connect((self.src, "strobe"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.tx, self.chan, self.rx, self.depkt, self.null_snk)

if __name__ == '__main__':
    tb = test_tb()
    tb.start()
    time.sleep(3)
    tb.stop()
    tb.wait()
