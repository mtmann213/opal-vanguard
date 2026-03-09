import os
import sys
import numpy as np
from gnuradio import gr, blocks, pdu, digital
import pmt
import time
import yaml

# Add current dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from packetizer import packetizer
from depacketizer import depacketizer

def test_level7_ofdm():
    config_path = "mission_configs/level7_ofdm_master.yaml"
    print(f"--- [TESTING LEVEL 7] {config_path} ---")
    
    with open(config_path, 'r') as f:
        cfg = yaml.safe_load(f)

    class OFDMTest(gr.top_block):
        def __init__(self):
            gr.top_block.__init__(self)
            
            # Level 7 Parameters
            self.pkt = packetizer(config_path=config_path)
            self.depkt = depacketizer(config_path=config_path)
            
            # Message debug to capture output
            self.msg_debug = blocks.message_debug()
            self.null_sink = blocks.null_sink(gr.sizeof_char)
            
            # Connect Packetizer to Depacketizer directly (Digital Loopback)
            # Packetizer for Level 7 outputs packed bytes for OFDM
            self.p2s = pdu.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
            self.b2b = blocks.packed_to_unpacked_bb(1, gr.GR_MSB_FIRST)
            
            self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
            self.connect(self.p2s, self.b2b, self.depkt)
            self.connect(self.depkt, self.null_sink)
            self.msg_connect((self.depkt, "out"), (self.msg_debug, "store"))
            
        def send_pdu(self, payload_bytes):
            meta = pmt.make_dict()
            blob = pmt.init_u8vector(len(payload_bytes), list(payload_bytes))
            pdu_msg = pmt.cons(meta, blob)
            self.pkt.handle_msg(pdu_msg)

    tb = OFDMTest()
    tb.start()
    
    # Test with a large payload (simulating OFDM capacity)
    test_payload = b"OPAL_VANGUARD_LEVEL_7_OFDM_VERIFICATION_TEST_" + b"X" * 200
    print(f"Sending {len(test_payload)} byte payload...")
    tb.send_pdu(test_payload)
    
    success = False
    start_time = time.time()
    while time.time() - start_time < 10.0:
        if tb.msg_debug.num_messages() > 0:
            recv_payload = bytes(pmt.u8vector_elements(pmt.cdr(tb.msg_debug.get_message(0))))
            if test_payload in recv_payload:
                print(f"[OK] Received Payload Match (Len: {len(recv_payload)})")
                success = True
                break
        time.sleep(0.1)
    
    tb.stop()
    tb.wait()
    
    if success:
        print("--- [LEVEL 7 PASS] ---")
    else:
        print("--- [LEVEL 7 FAIL] ---")
    return success

if __name__ == "__main__":
    test_level7_ofdm()
