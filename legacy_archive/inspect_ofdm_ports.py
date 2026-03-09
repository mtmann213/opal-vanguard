from gnuradio import digital
import pmt

rx = digital.ofdm_rx(64, 16, "packet_len")
in_ports = pmt.to_python(rx.message_ports_in())
out_ports = pmt.to_python(rx.message_ports_out())

print(f"Input ports: {in_ports}")
print(f"Output ports: {out_ports}")
