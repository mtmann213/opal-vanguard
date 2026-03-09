import struct
import os
import yaml
import numpy as np
import sys
import pmt

# Add src to path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from packetizer import packetizer
from depacketizer import depacketizer

# 1. Setup
config_path = "mission_configs/level6_link16.yaml"
pkt = packetizer(config_path=config_path, src_id=1)
depkt = depacketizer(config_path=config_path, src_id=1, ignore_self=False)

# 2. Create Mission Data
payload = b"TEST_PAYLOAD_12345"
msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(payload), list(payload)))

# 3. Packetize
pkt.message_port_pub = lambda p, m: setattr(pkt, 'last_out', m)
pkt.handle_msg(msg)
bits = list(pmt.u8vector_elements(pmt.cdr(pkt.last_out)))

print(f"Bits generated: {len(bits)}")

# 4. Depacketize
in_items = [np.array(bits, dtype=np.uint8)]
out_items = [np.zeros(len(bits), dtype=np.uint8)]

depkt.produce = lambda p, n: None
depkt.consume = lambda p, n: None
depkt.nitems_written = lambda p: 0
depkt.add_item_tag = lambda p, o, k, v: None
depkt.message_port_pub = lambda p, m: setattr(depkt, 'last_recv', m)

depkt.general_work(in_items, out_items)

# 5. Verify
if hasattr(depkt, 'last_recv'):
    recv_payload = bytes(pmt.u8vector_elements(pmt.cdr(depkt.last_recv)))
    print(f"Recovered Payload: {recv_payload}")
    if payload in recv_payload:
        print("SUCCESS: Binary Transparency Confirmed.")
    else:
        print(f"FAILURE: Payload Mismatch! Received: {recv_payload}")
else:
    print("FAILURE: No packet recovered by depacketizer.")
