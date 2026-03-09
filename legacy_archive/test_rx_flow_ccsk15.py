import numpy as np
from gnuradio import gr, blocks, digital, filter, channels, analog
import pmt
import time
import yaml
from packetizer import packetizer
from depacketizer import depacketizer

with open('mission_configs/level7_ofdm_master.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

class MockPacketizer(packetizer):
    def __init__(self):
        super().__init__("mission_configs/level7_ofdm_master.yaml")
        self.output_msg = None
    def message_port_pub(self, port, msg):
        self.output_msg = msg

p = MockPacketizer()
# Test with HEARTBEAT from ALPHA
msg_str = "HEARTBEAT FROM ALPHA".encode()
msg_in = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(msg_str), list(msg_str)))
p.handle_msg(msg_in)
burst = list(pmt.u8vector_elements(pmt.cdr(p.output_msg)))

class MockDepacketizer(depacketizer):
    def __init__(self):
        super().__init__("mission_configs/level7_ofdm_master.yaml", ignore_self=False)
        self.output_msg = None
        self.bit_count = 0
        self.sync_found = False
    def general_work(self, input_items, output_items):
        in0 = input_items[0]; n = len(in0)
        self.bit_count += n
        if self.state == "COLLECT" and not self.sync_found:
            print(f"SYNC FOUND after {self.bit_count} bits!")
            self.sync_found = True
        return super().general_work(input_items, output_items)
        
    def message_port_pub(self, port, msg):
        if pmt.symbol_to_string(port) == "out":
            self.output_msg = msg
            print("DEPACKETIZER SUCCESS:", bytes(pmt.u8vector_elements(pmt.cdr(msg))))
        elif pmt.symbol_to_string(port) == "diagnostics":
            pass

class test_tb(gr.top_block):
    def __init__(self):
        super().__init__()
        samp_rate = 500000
        sps = 10
        
        # Test if the length tag scaling is causing usrp sink to chop the packet?
        self.src = blocks.message_strobe(pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(burst), burst)), 500)
        self.p2s = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        constel = digital.constellation_bpsk().base()
        self.unpack_tx = blocks.unpack_k_bits_bb(8)
        self.mod_a = digital.chunks_to_symbols_bc(constel.points(), 1)
        
        # The USRP expects continuous bursts. When we are generating massive bursts with 500 Ksps,
        # we might be taking too long to generate them, causing underflows.
        # But user didn't see underflows this time.
        
        nfilts = 32
        rrc_taps = filter.firdes.root_raised_cosine(sps, sps, 1.0, 0.35, 11*sps)
        self.tx_filter = filter.interp_fir_filter_ccc(sps, rrc_taps)
        
        self.mult_len = blocks.tagged_stream_multiply_length(gr.sizeof_gr_complex, "packet_len", 8 * sps)
        
        # INCREASE NOISE SIGNIFICANTLY to see if link breaks at 85dB gain equivalent
        self.chan = channels.channel_model(noise_voltage=0.8)
        
        self.agc = analog.agc_cc(1e-4, 1.0, 1.0); self.agc.set_max_gain(65536)
        rx_rrc_taps = filter.firdes.root_raised_cosine(1.0, sps, 1.0, 0.35, 11*sps)
        self.bpsk_rx_filter = filter.fir_filter_ccf(1, rx_rrc_taps)
        self.bpsk_sync = digital.symbol_sync_cc(digital.TED_MUELLER_AND_MULLER, sps, 0.045, 1.0, 1.0, 1.5, 1, constel, digital.IR_MMSE_8TAP, 128, [])
        self.costas = digital.costas_loop_cc(0.06, 2, False)
        
        self.demod_b = digital.constellation_decoder_cb(constel)
        self.depkt = MockDepacketizer()
        self.null_snk = blocks.null_sink(gr.sizeof_char)
        
        self.msg_connect((self.src, "strobe"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.unpack_tx, self.mod_a, self.tx_filter, self.mult_len, self.chan)
        self.connect(self.chan, self.agc, self.bpsk_rx_filter, self.bpsk_sync, self.costas, self.demod_b, self.depkt, self.null_snk)

if __name__ == '__main__':
    tb = test_tb()
    tb.start()
    time.sleep(3)
    tb.stop()
    tb.wait()
