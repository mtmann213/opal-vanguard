import sys

with open('src/usrp_transceiver.py', 'r') as f:
    code = f.read()

# Replace FreqDiffMapper
old_mapper = """class FreqDiffMapper(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, "FreqDiffMapper", in_sig=[np.uint8], out_sig=[np.complex64])
        self.phase = 1.0+0j; self.count = 0
    def work(self, input_items, output_items):
        in0, out = input_items[0], output_items[0]
        # Propagate tags to ensure C++ allocator sees packet_len
        tags = self.get_tags_in_window(0, 0, len(in0))
        for tag in tags: self.add_item_tag(0, self.nitems_written(0) + (tag.offset - self.nitems_read(0)), tag.key, tag.value)
        for i in range(len(in0)):
            if self.count % 48 == 0: self.phase = 1.0+0j
            elif in0[i] == 1: self.phase *= -1.0
            out[i] = self.phase; self.count += 1
        return len(in0)"""

new_mapper = """class FreqDiffMapper(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, "FreqDiffMapper", in_sig=[np.uint8], out_sig=[np.complex64])
        self.phase = 1.0+0j
    def work(self, input_items, output_items):
        in0, out = input_items[0], output_items[0]
        tags = self.get_tags_in_window(0, 0, len(in0))
        for tag in tags: self.add_item_tag(0, self.nitems_written(0) + (tag.offset - self.nitems_read(0)), tag.key, tag.value)
        for i in range(len(in0)):
            if in0[i] == 1: self.phase *= -1.0
            out[i] = self.phase
        return len(in0)"""

# Replace FreqDiffDemapper
old_demapper = """class FreqDiffDemapper(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, "FreqDiffDemapper", in_sig=[np.complex64], out_sig=[np.uint8])
        self.prev_sym = 1.0+0j; self.count = 0
    def work(self, input_items, output_items):
        in0, out = input_items[0], output_items[0]
        for i in range(len(in0)):
            if self.count % 48 == 0: out[i] = 0
            else:
                diff = in0[i] * np.conj(self.prev_sym)
                out[i] = 1 if diff.real < 0 else 0
            self.prev_sym = in0[i]; self.count += 1
        return len(in0)"""

new_demapper = """class FreqDiffDemapper(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, "FreqDiffDemapper", in_sig=[np.complex64], out_sig=[np.uint8])
        self.prev_sym = 1.0+0j
    def work(self, input_items, output_items):
        in0, out = input_items[0], output_items[0]
        for i in range(len(in0)):
            diff = in0[i] * np.conj(self.prev_sym)
            out[i] = 1 if diff.real < 0 else 0
            self.prev_sym = in0[i]
        return len(in0)"""

code = code.replace(old_mapper, new_mapper)
code = code.replace(old_demapper, new_demapper)

with open('src/usrp_transceiver.py', 'w') as f:
    f.write(code)
