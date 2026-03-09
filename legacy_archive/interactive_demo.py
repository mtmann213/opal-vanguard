#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Interactive Demo Script

import os
import sys
import numpy as np
import pmt
import time

# Add src to path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from packetizer import packetizer
from whitener import whitener
from hop_controller import lfsr_hop_generator

def run_demo():
    print("="*40)
    print("   OPAL VANGUARD INTERACTIVE DEMO   ")
    print("="*40)
    
    # Initialize blocks
    pkt = packetizer()
    whit = whitener(seed=0x7F)
    hop = lfsr_hop_generator(seed=0xACE)
    
    # We need a way to capture the output of the packetizer.
    # Since packetizer uses message_port_pub, we'll mock its message_port_pub
    # to capture the output packet.
    last_packet = [None]
    def mock_pub(port, msg):
        last_packet[0] = msg
    pkt.message_port_pub = mock_pub
    
    # Same for hop controller
    last_freq = [None]
    def mock_hop_pub(port, msg):
        last_freq[0] = pmt.to_double(msg)
    hop.message_port_pub = mock_hop_pub

    while True:
        try:
            print("\nOptions: [1] Send Payload [2] Trigger Hop [q] Quit")
            choice = input("Select: ").strip().lower()
            
            if choice == 'q':
                break
            elif choice == '1':
                payload_str = input("Enter payload string (e.g., 'Hello'): ").strip()
                payload_bytes = payload_str.encode('utf-8')
                
                # Step 1: Packetize
                meta = pmt.make_dict()
                blob = pmt.init_u8vector(len(payload_bytes), list(payload_bytes))
                pdu = pmt.cons(meta, blob)
                
                pkt.handle_msg(pdu)
                packet_msg = last_packet[0]
                
                if packet_msg:
                    packet_bytes = bytes(pmt.u8vector_elements(pmt.cdr(packet_msg)))
                    print(f"\n[Packetizer] Generated Packet (Hex): {packet_bytes.hex(' ')}")
                    
                    # Step 2: Whiten (simulating bitstream)
                    # Convert bytes to bits for the whitener (as it expects 0/1 bits)
                    bits = []
                    for b in packet_bytes:
                        for i in range(8):
                            bits.append((b >> (7-i)) & 1)
                    
                    in_bits = np.array(bits, dtype=np.uint8)
                    out_bits = np.zeros(len(in_bits), dtype=np.uint8)
                    whit.work([in_bits], [out_bits])
                    
                    print(f"[Whitener]   First 16 whitened bits: {list(out_bits[:16])}")
                    
            elif choice == '2':
                # Step 3: Frequency Hop
                hop.handle_trigger(pmt.PMT_T)
                if last_freq[0]:
                    print(f"\n[Hop Controller] New Frequency: {last_freq[0]/1e6:.3f} MHz")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

    print("\nExiting Demo.")

if __name__ == "__main__":
    run_demo()
