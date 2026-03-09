import sys

with open('src/usrp_transceiver.py', 'r') as f:
    code = f.read()

old_rx = """            # RX Path: Stream-based CP Stripping -> Vectorize -> FFT -> Equalize -> Extract Data Carriers
            self.keep = blocks.keep_m_in_n(gr.sizeof_gr_complex, fft_len, fft_len+cp_len, cp_len)
            self.s2v = blocks.stream_to_vector(gr.sizeof_gr_complex, fft_len)
            self.fft_rx = fft.fft_vcc(fft_len, True, (), True, 1)

            # Custom Phase/Frequency Equalizer using Pilot Tones
            self.eq = OFDMEqualizer(fft_len, pilot_carriers[0], pilot_symbols[0])
            
            # Custom tag-less Carrier Extractor (Replaces fragile ofdm_serializer)
            self.extractor = OFDMCarrierExtractor(fft_len, data_carriers[0])
            self.v2s_rx = blocks.vector_to_stream(gr.sizeof_gr_complex, 48)
            self.diff_demap = FreqDiffDemapper()
            sync_hex = "3D4C5B6AACE12345"; sync_bits = "".join(f"{int(c, 16):04b}" for c in sync_hex)
            sync_inv = "".join('1' if b=='0' else '0' for b in sync_bits)
            self.corr_norm = digital.correlate_access_code_tag_bb(sync_bits, 12, "sync_found")
            self.corr_inv = digital.correlate_access_code_tag_bb(sync_inv, 12, "sync_inverted")
            
            self.connect(self.usrp_source, self.rx_filter, self.rx_delay, self.keep, self.s2v, self.fft_rx, self.eq, self.extractor, self.v2s_rx, self.diff_demap, self.corr_norm, self.corr_inv, self.depkt_b)"""

new_rx = """            # RX Path: Stream-based CP Stripping -> Vectorize -> FFT -> Extract
            self.keep = blocks.keep_m_in_n(gr.sizeof_gr_complex, fft_len, fft_len+cp_len, cp_len)
            self.s2v = blocks.stream_to_vector(gr.sizeof_gr_complex, fft_len)
            self.fft_rx = fft.fft_vcc(fft_len, True, (), True, 1)
            self.extractor = OFDMCarrierExtractor(fft_len, data_carriers[0])
            self.v2s_rx = blocks.vector_to_stream(gr.sizeof_gr_complex, 48)
            self.sub_demod = digital.constellation_decoder_cb(constel)
            
            self.connect(self.usrp_source, self.rx_filter, self.rx_delay, self.keep, self.s2v, self.fft_rx, self.extractor, self.v2s_rx, self.sub_demod, self.depkt_b)"""

code = code.replace(old_rx, new_rx)

with open('src/usrp_transceiver.py', 'w') as f:
    f.write(code)
