import sys

with open('src/depacketizer.py', 'r') as f:
    code = f.read()

# Replace the whole general_work method for clarity
old_work = """    def general_work(self, input_items, output_items):
        in0 = input_items[0]; n = len(in0)
        tags = self.get_tags_in_window(0, 0, n)
        
        is_ofdm = self.cfg['physical'].get('modulation', 'GFSK') == 'OFDM'
        is_tactical = ("LINK-16" in self.fec_mode or "LEVEL_6" in self.fec_mode or "LEVEL_7" in self.fec_mode or is_ofdm)

        found_now = False
        for tag in tags:
            tag_key = pmt.symbol_to_string(tag.key)
            if tag_key in ["sync_found", "sync_inverted"]:
                tag_offset = tag.offset - self.nitems_read(0)
                if tag_offset >= 0 and tag_offset < n:
                    self.state = "COLLECT"
                    self.recovered_bits = []
                    self.is_inverted = (tag_key == "sync_inverted")
                    self.nrzi.reset() 
                    self.scrambler.reset(); self.ccsk_buf = []
                    in0 = in0[tag_offset:]; found_now = True
                    self.last_sync_time = time.time()
                    break

        # Scanning Logic
        if not found_now and (time.time() - self.last_sync_time) > 0.1:
            if self.cfg['physical'].get('modulation') == 'OFDM':
                self.current_delay = (self.current_delay + 1) % 96
                self.message_port_pub(pmt.intern("scan_control"), pmt.from_long(self.current_delay))
                self.last_sync_time = time.time()

        if self.state == "COLLECT":
            for bit in in0:
                rx_bit = (int(bit) & 1) ^ (1 if self.is_inverted else 0)
                
                if self.use_nrzi and not is_tactical:
                    decoded = self.nrzi.decode([rx_bit])
                    if not decoded: continue
                    rx_bit = decoded[0]

                if self.use_ccsk:
                    self.ccsk_buf.append(rx_bit)
                    if len(self.ccsk_buf) >= 32:
                        sym, _ = self.ccsk.decode_chips(self.ccsk_buf)
                        for j in range(5): self.recovered_bits.append((sym >> (4-j)) & 1)
                        self.ccsk_buf = []
                else: self.recovered_bits.append(rx_bit)
                
                if len(self.recovered_bits) >= (self.frame_size * 8):
                    self.process_packet(self.frame_size)
                    self.state = "SEARCH"
                    break

        self.consume(0, n); return 0"""

new_work = """    def general_work(self, input_items, output_items):
        in0 = input_items[0]; n = len(in0)
        tags = self.get_tags_in_window(0, 0, n)
        
        is_ofdm = self.cfg['physical'].get('modulation', 'GFSK') == 'OFDM'
        is_tactical = ("LINK-16" in self.fec_mode or "LEVEL_6" in self.fec_mode or "LEVEL_7" in self.fec_mode or is_ofdm)

        # 1. Handle Sync Tags
        found_now = False
        for tag in tags:
            tag_key = pmt.symbol_to_string(tag.key)
            if tag_key in ["sync_found", "sync_inverted"]:
                tag_offset = tag.offset - self.nitems_read(0)
                if tag_offset >= 0 and tag_offset < n:
                    self.state = "COLLECT"; self.recovered_bits = []
                    self.is_inverted = (tag_key == "sync_inverted")
                    self.nrzi.reset(); self.scrambler.reset(); self.ccsk_buf = []
                    in0 = in0[tag_offset:]; found_now = True
                    self.last_sync_time = time.time(); break

        # 2. Scanning Logic (OFDM Only)
        if not found_now and (time.time() - self.last_sync_time) > 0.1:
            if is_ofdm:
                self.current_delay = (self.current_delay + 1) % 96
                self.message_port_pub(pmt.intern("scan_control"), pmt.from_long(self.current_delay))
                self.last_sync_time = time.time()

        # 3. Legacy Bit Search (Non-OFDM only, if no tags found)
        if not is_ofdm and self.state == "SEARCH":
            sync_val = 0x3D4C5B6AACE12345 if is_tactical else 0x3D4C5B6A
            sync_len = 64 if is_tactical else 32
            for i in range(n):
                bit = int(in0[i]) & 1
                self.bit_buf = ((self.bit_buf << 1) | bit) & 0xFFFFFFFFFFFFFFFF
                buf64 = self.bit_buf; buf32 = self.bit_buf & 0xFFFFFFFF
                found_sync = False
                if is_tactical:
                    if (buf64 ^ sync_val).bit_count() <= 4: self.is_inverted, found_sync = False, True
                    elif (buf64 ^ (0xFFFFFFFFFFFFFFFF ^ sync_val)).bit_count() <= 4: self.is_inverted, found_sync = True, True
                else:
                    if (buf32 ^ sync_val).bit_count() <= 2: self.is_inverted, found_sync = False, True
                    elif (buf32 ^ (0xFFFFFFFF ^ sync_val)).bit_count() <= 2: self.is_inverted, found_sync = True, True
                if found_sync:
                    self.state = "COLLECT"; self.recovered_bits = []; self.nrzi.reset(); self.scrambler.reset(); self.ccsk_buf = []
                    in0 = in0[i+1:]; break

        # 4. Bit Collection
        if self.state == "COLLECT":
            for bit in in0:
                rx_bit = (int(bit) & 1) ^ (1 if self.is_inverted else 0)
                if self.use_nrzi and not is_tactical:
                    decoded = self.nrzi.decode([rx_bit])
                    if not decoded: continue
                    rx_bit = decoded[0]
                if self.use_ccsk:
                    self.ccsk_buf.append(rx_bit)
                    if len(self.ccsk_buf) >= 32:
                        sym, _ = self.ccsk.decode_chips(self.ccsk_buf)
                        for j in range(5): self.recovered_bits.append((sym >> (4-j)) & 1)
                        self.ccsk_buf = []
                else: self.recovered_bits.append(rx_bit)
                if len(self.recovered_bits) >= (self.frame_size * 8):
                    self.process_packet(self.frame_size); self.state = "SEARCH"; break

        self.consume(0, n); return 0"""

if old_work in code:
    code = code.replace(old_work, new_work)
    with open('src/depacketizer.py', 'w') as f: f.write(code)
    print("SUCCESS")
else:
    print("FAIL: Content mismatch")
