from packetizer import packetizer

p = packetizer("mission_configs/level7_ofdm_master.yaml")
import pmt
import struct
# Try sending a message larger than (1024 * 11 / 15) which is ~750 bytes
# To see if it truncates
msg_str = b"A" * 800
msg_in = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(msg_str), list(msg_str)))

try:
    p.handle_msg(msg_in)
    print("Packet generated successfully. Length of out_bits/packed_bytes:", pmt.length(pmt.cdr(p.output_msg)) if hasattr(p, 'output_msg') else "N/A")
except Exception as e:
    print("Error:", e)
    
# But what about the heartbeats? They are very short.
# So truncation shouldn't break the heartbeat!
