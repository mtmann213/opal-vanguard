import numpy as np
from gnuradio import gr, blocks, pdu, digital, filter
import pmt
import time
import yaml
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from packetizer import packetizer
from depacketizer import depacketizer

def test_level1_modem():
    config_path = "mission_configs/level1_soft_link.yaml"
    print(f"--- [TESTING LEVEL 1 MODEM] {config_path} ---")
    
    with open(config_path, 'r') as f:
        cfg = yaml.safe_load(f)
    
    samp_rate = 2000000
    sps = cfg['physical'].get('samples_per_symbol', 10)
    bit_rate = samp_rate / sps
    sens = (2.0 * np.pi * cfg['physical'].get('freq_dev', 25000)) / samp_rate
    bt = 0.35
    
    class Level1ModemTest(gr.top_block):
        def __init__(self):
            gr.top_block.__init__(self)
            
            self.pkt = packetizer(config_path=config_path)
            self.depkt = depacketizer(config_path=config_path)
            
            # v19.58: Use 'bit_count' to match packetizer output
            self.p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "bit_count")
            
            # TX Path
            # v19.58: GFSK mod in digital loopback doesn't strictly need lengths 
            # if we are just testing the logic chain.
            self.mod = digital.gfsk_mod(sps, sens, bt, False, False, False)
            
            # Channel
            self.throttle = blocks.throttle(gr.sizeof_gr_complex, samp_rate)
            
            # RX Path
            self.rx_filter = filter.fir_filter_ccf(1, filter.firdes.low_pass(1.0, samp_rate, 250e3, 50e3))
            self.demod = digital.gfsk_demod(sps, sens, 0.2, 0.5, 0.01, 0.0)
            
            self.msg_debug = blocks.message_debug()
            
            self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
            # Connect the chain
            self.connect(self.p2s, self.mod, self.throttle, self.rx_filter, self.demod, self.depkt)
            self.msg_connect((self.depkt, "out"), (self.msg_debug, "store"))
            
        def send_msg(self, payload):
            meta = pmt.make_dict()
            meta = pmt.dict_add(meta, pmt.intern("type"), pmt.from_long(0))
            meta = pmt.dict_add(meta, pmt.intern("seq"), pmt.from_long(123))
            blob = pmt.init_u8vector(len(payload), list(payload))
            self.pkt.handle_msg(pmt.cons(meta, blob))

    tb = Level1ModemTest()
    tb.start()
    
    test_payload = b"LEVEL_1_MODEM_TEST"
    print(f"Sending: {test_payload}")
    for _ in range(3):
        tb.send_msg(test_payload)
        time.sleep(0.2)
    
    success = False
    start_time = time.time()
    while time.time() - start_time < 3.0:
        if tb.msg_debug.num_messages() > 0:
            success = True
            break
        time.sleep(0.1)
    
    tb.stop()
    tb.wait()
    
    if success:
        print("\033[92m[PASS]\033[0m Level 1 modem loopback successful.")
    else:
        print("\033[91m[FAIL]\033[0m Level 1 modem loopback failed.")

if __name__ == "__main__":
    test_level1_modem()
