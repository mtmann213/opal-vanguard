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
        
        # Use OFDM parameters that fit in small buffers
        fft_len = 64
        cp_len = 16
        
        # OFDM TX
        self.tx = digital.ofdm_tx(fft_len=fft_len, cp_len=cp_len, packet_length_tag_key="packet_len")
        
        # Channel
        self.chan = channels.channel_model(noise_voltage=0.0)
        
        # OFDM RX
        self.rx = digital.ofdm_rx(fft_len=fft_len, cp_len=cp_len, packet_length_tag_key="packet_len")
        
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
        
        # KEY FIX: Break the min_noutput_items constraint by using a stream demuxer or throttle?
        # Actually, the USRP Sink is the one requesting the large buffer. 
        # In this sim, it's the depacketizer.
        # Let's set min_noutput_items to 1 on ALL blocks in the RX chain.
        
        self.msg_connect((self.src, "strobe"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.tx, self.chan, self.rx, self.depkt, self.null_snk)

if __name__ == '__main__':
    tb = test_tb()
    # tb.rx.set_min_noutput_items(1) # digital.ofdm_rx is a hierarchical block, can't set it directly easily
    tb.start()
    time.sleep(3)
    tb.stop()
    tb.wait()
