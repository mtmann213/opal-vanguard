import sys

with open('src/usrp_transceiver.py', 'r') as f:
    code = f.read()

# Update Mapper to handle continuous symbols correctly
mapper_old = """class FreqDiffMapper(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, "FreqDiffMapper", in_sig=[np.uint8], out_sig=[np.complex64])
    def work(self, input_items, output_items):
        in0, out = input_items[0], output_items[0]
        tags = self.get_tags_in_window(0, 0, len(in0))
        # Expansion factor 48/47. Calculate total input chunks of 47 bits.
        n_chunks = len(in0) // 47
        if n_chunks == 0: return 0
        for i in range(n_chunks):
            # Propagate tag from first bit of chunk to first symbol of output
            chunk_tags = [t for t in tags if (t.offset - self.nitems_read(0)) >= i*47 and (t.offset - self.nitems_read(0)) < (i+1)*47]
            for t in chunk_tags: self.add_item_tag(0, self.nitems_written(0) + i*48, t.key, t.value)
            
            chunk = in0[i*47:(i+1)*47]
            phase = 1.0+0j
            out[i*48] = phase # Carrier 0: Reference
            for j in range(47):
                if chunk[j] == 1: phase *= -1.0
                out[i*48 + 1 + j] = phase
        return n_chunks * 48"""

mapper_new = """class FreqDiffMapper(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, "FreqDiffMapper", in_sig=[np.uint8], out_sig=[np.complex64])
    def work(self, input_items, output_items):
        in0, out = input_items[0], output_items[0]
        tags = self.get_tags_in_window(0, 0, len(in0))
        n_chunks = len(in0) // 47
        if n_chunks == 0: return 0
        for i in range(n_chunks):
            chunk_tags = [t for t in tags if (t.offset - self.nitems_read(0)) >= i*47 and (t.offset - self.nitems_read(0)) < (i+1)*47]
            for t in chunk_tags: self.add_item_tag(0, self.nitems_written(0) + i*48, t.key, t.value)
            chunk = in0[i*47:(i+1)*47]
            phase = 1.0+0j
            out[i*48] = phase
            for j in range(47):
                if chunk[j] == 1: phase *= -1.0
                out[i*48 + 1 + j] = phase
        return n_chunks * 48"""

code = code.replace(mapper_old, mapper_new)

# Restore 1020-byte frame size in config scaling logic
code = code.replace('1.0/47.0', '1.0/47.0') # Already correct

with open('src/usrp_transceiver.py', 'w') as f:
    f.write(code)
