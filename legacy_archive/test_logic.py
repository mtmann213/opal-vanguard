#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Logic Test Script

import numpy
from gnuradio import gr
from gnuradio import blocks
import pmt
import time
import os
import sys

# Ensure current directory is in sys.path to import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hop_controller import lfsr_hop_generator as HopController
from whitener import whitener as Whitener

def test_hop_controller():
    print("Testing Hop Controller (LFSR)...")
    center_freq = 915e6
    num_channels = 50
    spacing = 500e3
    
    class MsgTest(gr.top_block):
        def __init__(self):
            gr.top_block.__init__(self)
            self.ctrl = HopController(seed=0xACE, num_channels=num_channels, center_freq=center_freq, channel_spacing=spacing)
            self.msg_debug = blocks.message_debug()
            self.msg_connect((self.ctrl, "freq"), (self.msg_debug, "print"))
            
        def trigger(self):
            self.ctrl.handle_trigger(pmt.PMT_T)

    tb = MsgTest()
    tb.start()
    
    print("Output frequencies (first 5 hops):")
    for _ in range(5):
        tb.trigger()
        time.sleep(0.01)
        
    tb.stop()
    tb.wait()
    print("Hop Controller test done.\n")

def test_whitener():
    print("Testing Whitener (x^7 + x^4 + 1)...")
    input_bits = numpy.array([0, 0, 0, 0, 0, 0, 0, 0], dtype=numpy.uint8)
    w = Whitener(seed=0x7F)
    
    out = numpy.zeros(len(input_bits), dtype=numpy.uint8)
    w.work([input_bits], [out])
    
    print(f"Input bits:  {list(input_bits)}")
    print(f"Output bits: {list(out)}")
    
    if out[0] == 1:
        print("Whitener logic check passed (first bit).")
    else:
        print(f"Whitener logic check FAILED. Got {out[0]}, expected 1.")

if __name__ == "__main__":
    test_hop_controller()
    test_whitener()
