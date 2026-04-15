#!/usr/bin/env python3
from gnuradio import gr
import pmt
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class aes_hop_generator(gr.basic_block):
    def __init__(
        self,
        key=b"\x00" * 32,
        num_channels=50,
        center_freq=915e6,
        channel_spacing=150e3,
    ):
        gr.basic_block.__init__(
            self, name="aes_hop_generator", in_sig=None, out_sig=None
        )
        self.num_channels, self.center_freq, self.channel_spacing, self.key = (
            num_channels,
            center_freq,
            channel_spacing,
            key,
        )
        self.counter, self.blacklist, self.backend = 0, [], default_backend()
        self.message_port_register_in(pmt.intern("trigger"))
        self.set_msg_handler(pmt.intern("trigger"), self.handle_trigger)
        self.message_port_register_in(pmt.intern("blacklist"))
        self.set_msg_handler(pmt.intern("blacklist"), self.handle_blacklist)
        self.message_port_register_in(pmt.intern("set_seed"))
        self.set_msg_handler(pmt.intern("set_seed"), self.handle_set_seed)
        self.message_port_register_out(pmt.intern("freq"))

    def handle_set_seed(self, msg):
        seed = pmt.to_long(msg)
        self.counter = seed & 0xFFFFFFFFFFFFFFFF

    def handle_blacklist(self, msg):
        if pmt.is_u8vector(msg):
            self.blacklist = list(pmt.u8vector_elements(msg))

    def handle_trigger(self, msg):
        nonce = struct.pack(">QQ", 0, self.counter)
        cipher = Cipher(algorithms.AES(self.key), modes.ECB(), backend=self.backend)
        enc = cipher.encryptor()
        keystream = enc.update(nonce) + enc.finalize()
        raw_idx = struct.unpack(">I", keystream[:4])[0] % self.num_channels

        final_idx = raw_idx
        if self.blacklist and raw_idx in self.blacklist:
            for i in range(1, self.num_channels):
                candidate = (raw_idx + i) % self.num_channels
                if candidate not in self.blacklist:
                    final_idx = candidate
                    break

        freq = (
            self.center_freq
            + (final_idx - (self.num_channels // 2)) * self.channel_spacing
        )

        out_dict = pmt.make_dict()
        out_dict = pmt.dict_add(out_dict, pmt.intern("freq"), pmt.from_double(freq))
        out_dict = pmt.dict_add(out_dict, pmt.intern("time"), pmt.from_double(0.0))
        self.message_port_pub(pmt.intern("freq"), out_dict)

        self.counter = (self.counter + 1) & 0xFFFFFFFFFFFFFFFF

    def work(self, i, o):
        return 0
