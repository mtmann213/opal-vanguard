import time
import struct
import numpy as np
from src.hop_generator_tod import tod_hop_generator
from gnuradio import gr
import pmt

class MockHopGen(tod_hop_generator):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    def message_port_pub(self, port, msg):
        pass

gen = MockHopGen(num_channels=6, dwell_ms=100) # Fast dwell for testing

for i in range(5):
    now = time.time()
    epoch = int(now / gen.dwell_sec)
    
    nonce = struct.pack(">QQ", 0, epoch)
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    cipher = Cipher(algorithms.AES(gen.key), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    keystream = encryptor.update(nonce) + encryptor.finalize()
    
    rand_val = struct.unpack(">I", keystream[:4])[0]
    raw_idx = rand_val % gen.num_channels
    print(f"Time: {now:.2f} | Epoch: {epoch} | Chan: {raw_idx}")
    time.sleep(0.15)
