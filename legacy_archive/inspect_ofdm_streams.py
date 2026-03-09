from gnuradio import digital
rx = digital.ofdm_rx(64, 16, "packet_len")
print(f"Input size: {rx.input_signature().sizeof_item(0)}")
print(f"Output size: {rx.output_signature().sizeof_item(0)}")
