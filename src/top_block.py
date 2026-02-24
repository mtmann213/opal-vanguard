#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Top Block Scaffold

import numpy
from gnuradio import gr
from gnuradio import blocks
from gnuradio import analog
from gnuradio import filter
from gnuradio import pmt
import time

# Import custom blocks (placeholders/implementations)
try:
    from hop_controller import lfsr_hop_generator as HopController
    from whitener import whitener as Whitener
except ImportError:
    # If running from a different directory, handle imports accordingly.
    # For now, we assume they are in the same directory.
    pass

class OpalVanguardTopBlock(gr.top_block):
    """
    Opal Vanguard Project
    Modular FHSS Messaging System (900MHz ISM)
    """
    def __init__(self, center_freq=915e6, num_channels=50, channel_spacing=500e3):
        gr.top_block.__init__(self, "Opal Vanguard Top Block")

        # Parameters
        self.center_freq = center_freq
        self.num_channels = num_channels
        self.channel_spacing = channel_spacing

        # Blocks
        # 1. Hop Controller (LFSR-based)
        self.hop_ctrl = HopController(
            seed=0xACE, 
            num_channels=num_channels, 
            center_freq=center_freq, 
            channel_spacing=channel_spacing
        )

        # 2. Source (Example: Random Bytes)
        self.src = analog.random_source_b(0, 2, 1000)

        # 3. Whitener (x^7 + x^4 + 1)
        self.whitener = Whitener(mask=0x48, seed=0x7F)

        # 4. Sink (Placeholder for now, e.g., Null Sink)
        self.snk = blocks.null_sink(gr.sizeof_char)

        # Message Connections (for frequency control)
        # In a real flowgraph, hop_ctrl 'freq' would connect to a frequency sink or HW.
        # self.msg_connect((self.hop_ctrl, "freq"), (SOME_HW_SINK, "command"))

        # Stream Connections
        self.connect(self.src, self.whitener, self.snk)

    def trigger_hop(self):
        """Manually trigger a frequency hop."""
        self.hop_ctrl.handle_trigger(pmt.PMT_T)

def main():
    tb = OpalVanguardTopBlock()
    tb.start()
    
    print("Opal Vanguard Top Block Started.")
    print(f"Cycling through {tb.num_channels} channels in the 900MHz ISM Band.")
    
    try:
        while True:
            # Simple hop loop for demonstration
            tb.trigger_hop()
            time.sleep(0.1)  # 100ms hop interval
    except KeyboardInterrupt:
        tb.stop()
        tb.wait()
        print("
Exiting Opal Vanguard.")

if __name__ == '__main__':
    main()
