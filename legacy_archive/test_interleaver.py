from src.dsp_helper import MatrixInterleaver
import struct

# Simulate Link-16 parameters
rows = 32
packet_size = 320

interleaver = MatrixInterleaver(rows=rows)

# Create a mock packet with a clear header
# Header: src_id=1, m_type=0, seq=42, plen=100
header = struct.pack('BBBB', 1, 0, 42, 100)
payload = b"A" * (packet_size - 4)
packet = header + payload

print(f"Original Header: {packet[:4].hex()}")

# Interleave
interleaved = interleaver.interleave(packet)

# Deinterleave
deinterleaved = interleaver.deinterleave(interleaved)

print(f"Recovered Header: {deinterleaved[:4].hex()}")

if packet[:4] != deinterleaved[:4]:
    print("FAILURE: Interleaver scrambled the header!")
else:
    print("SUCCESS: Header survived interleaving.")
