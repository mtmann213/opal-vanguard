import sys

with open('src/usrp_transceiver.py', 'r') as f:
    code = f.read()

# Replace FreqDiffMapper
old_mapper = """class FreqDiffMapper(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, "FreqDiffMapper", in_sig=[np.uint8], out_sig=[np.complex64])
        self.phase = 1.0+0j
    def work(self, input_items, output_items):
        in0, out = input_items[0], output_items[0]
        tags = self.get_tags_in_window(0, 0, len(in0))
        for tag in tags: self.add_item_tag(0, self.nitems_written(0) + (tag.offset - self.nitems_read(0)), tag.key, tag.value)
        for i in range(len(in0)):
            if self.nitems_written(0) + i < 10: print(f"MAPPER BIT {self.nitems_written(0)+i}: {in0[i]}")
            if in0[i] == 1: self.phase *= -1.0
            out[i] = self.phase
        return len(in0)"""

new_mapper = """class FreqDiffMapper(gr.sync_block):
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

# Replace FreqDiffDemapper
old_demapper = """class FreqDiffDemapper(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, "FreqDiffDemapper", in_sig=[np.complex64], out_sig=[np.uint8])
        self.prev_sym = 1.0+0j
    def work(self, input_items, output_items):
        in0, out = input_items[0], output_items[0]
        for i in range(len(in0)):
            diff = in0[i] * np.conj(self.prev_sym)
            bit = 1 if diff.real < 0 else 0
            if self.nitems_written(0) + i < 10: print(f"DEMAPPER BIT {self.nitems_written(0)+i}: {bit}")
            out[i] = bit
            self.prev_sym = in0[i]
        return len(in0)"""

new_demapper = """class FreqDiffDemapper(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, "FreqDiffDemapper", in_sig=[np.complex64], out_sig=[np.uint8])
    def work(self, input_items, output_items):
        in0, out = input_items[0], output_items[0]
        n_chunks = len(in0) // 48
        if n_chunks == 0: return 0
        for i in range(n_chunks):
            chunk = in0[i*48:(i+1)*48]
            prev_sym = chunk[0]
            for j in range(1, 48):
                diff = chunk[j] * np.conj(prev_sym)
                out[i*47 + j - 1] = 1 if diff.real < 0 else 0
                prev_sym = chunk[j]
        return n_chunks * 47"""

code = code.replace(old_mapper, new_mapper)
code = code.replace(old_demapper, new_demapper)

# Update tag scaling in OFDM path
code = code.replace('self.tag_scale_sym = blocks.tagged_stream_multiply_length(gr.sizeof_gr_complex * fft_len, "packet_len", 1.0/48.0)',
                    'self.tag_scale_sym = blocks.tagged_stream_multiply_length(gr.sizeof_gr_complex * fft_len, "packet_len", 1.0/47.0)')

with open('src/usrp_transceiver.py', 'w') as f:
    f.write(code)
