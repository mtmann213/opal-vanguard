import numpy as np
from gnuradio import gr, blocks, digital
import pmt, time, yaml, os, sys

sys.path.append(os.path.join(os.getcwd(), 'src'))
from packetizer import packetizer
from depacketizer import depacketizer

class debug_depacketizer(depacketizer):
    def general_work(self, input_items, output_items):
        in0 = input_items[0]; n = len(in0)
        tags = self.get_tags_in_window(0, 0, n)
        for tag in tags:
            tag_key = pmt.symbol_to_string(tag.key)
            tag_offset = tag.offset - self.nitems_read(0)
            print(f"DEBUG: Found tag {tag_key} at local offset {tag_offset}")
            # Print the bits around the tag to see if syncword is correct
            start = max(0, tag_offset - 32)
            end = min(n, tag_offset + 32)
            bits_hex = "".join(str(int(b)) for b in in0[start:end])
            print(f"DEBUG: Bits around tag: ...{bits_hex}...")
        return super().general_work(input_items, output_items)

class test_tb(gr.top_block):
    def __init__(self, config):
        super().__init__()
        self.pkt = packetizer(config)
        self.depkt = debug_depacketizer(config)
        self.p2s = blocks.pdu_to_tagged_stream(gr.types.byte_t, "packet_len")
        
        sync_hex = "3D4C5B6A"
        sync_bits = "".join(f"{int(c, 16):04b}" for c in sync_hex)
        self.corr = digital.correlate_access_code_tag_bb(sync_bits, 0, "sync_found")
        
        self.msg_connect((self.pkt, "out"), (self.p2s, "pdus"))
        self.connect(self.p2s, self.corr, self.depkt, blocks.null_sink(gr.sizeof_char))

if __name__ == '__main__':
    tb = test_tb("mission_configs/level1_soft_link.yaml")
    tb.start()
    # Send a unique pattern to identify in the bitstream
    data = [0xDE, 0xAD, 0xBE, 0xEF] + [0x00]*6
    msg = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(data), data))
    tb.pkt.handle_msg(msg)
    time.sleep(1)
    tb.stop(); tb.wait()
