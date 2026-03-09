import sys

with open('src/usrp_transceiver.py', 'r') as f:
    code = f.read()

# Add diagnostics to Mapper
mapper_old = """        for i in range(len(in0)):
            if in0[i] == 1: self.phase *= -1.0
            out[i] = self.phase"""

mapper_new = """        for i in range(len(in0)):
            if self.nitems_written(0) + i < 10: print(f"MAPPER BIT {self.nitems_written(0)+i}: {in0[i]}")
            if in0[i] == 1: self.phase *= -1.0
            out[i] = self.phase"""

# Add diagnostics to Demapper
demapper_old = """        for i in range(len(in0)):
            diff = in0[i] * np.conj(self.prev_sym)
            out[i] = 1 if diff.real < 0 else 0
            self.prev_sym = in0[i]"""

demapper_new = """        for i in range(len(in0)):
            diff = in0[i] * np.conj(self.prev_sym)
            bit = 1 if diff.real < 0 else 0
            if self.nitems_written(0) + i < 10: print(f"DEMAPPER BIT {self.nitems_written(0)+i}: {bit}")
            out[i] = bit
            self.prev_sym = in0[i]"""

code = code.replace(mapper_old, mapper_new)
code = code.replace(demapper_old, demapper_new)

with open('src/usrp_transceiver.py', 'w') as f:
    f.write(code)
