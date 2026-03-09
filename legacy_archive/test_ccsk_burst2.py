import numpy as np
from gnuradio import gr, blocks, digital, filter, uhd
import pmt
import time

class test_tb(gr.top_block):
    def __init__(self):
        super().__init__()
        samp_rate = 500000
        sps = 10
        burst_size = 54560
        
        # Test: If we output UNPACKED bits (1 bit per byte) and pack them BEFORE pdu_to_tagged_stream?
        # NO, packetizer handles the generation.
        # But wait, packetizer generates a u8vector of size 54560 bytes!
        # pdu_to_tagged_stream takes that and outputs 54560 bytes.
        # It needs an output buffer of AT LEAST 54560 items.
        # The scheduler maxes out at 65536 for itemsize=1. So it CAN hold it.
        # BUT min_noutput_items is probably set too high somewhere, or it's trying to push the WHOLE packet through the whole chain.
        # If the packetizer outputs packed bytes, the size drops by 8x.
        
