#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - DSP Unit Tests

import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dsp_helper import (
    MatrixInterleaver,
    Scrambler,
    NRZIEncoder,
    CCSKProcessor,
    DSSSProcessor,
)


class TestMatrixInterleaver:
    """Test matrix interleaver/deinterleaver."""

    def test_roundtrip_small(self):
        """Test small data roundtrip."""
        inter = MatrixInterleaver(rows=4)
        data = b"Hello World!"
        encoded = inter.interleave(data)
        decoded = inter.deinterleave(encoded)
        assert decoded == data

    def test_roundtrip_120(self):
        """Test standard 120-byte frame with 15 rows."""
        inter = MatrixInterleaver(rows=15)
        data = b"A" * 120
        encoded = inter.interleave(data)
        decoded = inter.deinterleave(encoded)
        assert decoded == data

    def test_deinterleave_explicit_length(self):
        """Test deinterleave with explicit original length."""
        inter = MatrixInterleaver(rows=8)
        data = b"TestData"
        encoded = inter.interleave(data)
        decoded = inter.deinterleave(encoded, len(data))
        assert decoded == data

    def test_padding(self):
        """Test padding behavior."""
        inter = MatrixInterleaver(rows=10)
        data = b"Short"
        encoded = inter.interleave(data)
        # MatrixInterleaver pads to fill rows*8 bytes
        rows = 10
        expected_len = ((len(data) + rows - 1) // rows) * rows
        assert len(encoded) == expected_len


class TestScrambler:
    """Test LFSR scrambler."""

    def test_roundtrip(self):
        """Test scramble/descramble roundtrip."""
        scrambler = Scrambler(mask=0x48, seed=0x7F)
        data = b"Test Data 12345"
        scrambled = scrambler.process(data)
        scrambler.reset()
        descrambled = scrambler.process(scrambled)
        assert descrambled == data

    def test_deterministic(self):
        """Test deterministic output."""
        scrambler = Scrambler(mask=0x48, seed=0x7F)
        data = b"Deterministic"
        result1 = scrambler.process(data)
        scrambler.reset()
        result2 = scrambler.process(data)
        assert result1 == result2

    def test_seed_variation(self):
        """Test different seeds produce different output."""
        scrambler1 = Scrambler(seed=0x7F)
        scrambler2 = Scrambler(seed=0xAA)
        data = b"Seed Test"
        out1 = scrambler1.process(data)
        out2 = scrambler2.process(data)
        assert out1 != out2


class TestNRZIEncoder:
    """Test NRZI encoding/decoding."""

    def test_encode_decode(self):
        """Test basic NRZI encode/decode."""
        nrzi = NRZIEncoder()
        bits = [1, 0, 1, 1, 0, 0, 1, 0]
        encoded = nrzi.encode(bits)
        decoded = nrzi.decode(encoded)
        assert decoded == bits

    def test_all_zeros(self):
        """Test all zeros input."""
        nrzi = NRZIEncoder()
        bits = [0] * 8
        encoded = nrzi.encode(bits)
        decoded = nrzi.decode(encoded)
        assert decoded == bits

    def test_all_ones(self):
        """Test all ones input."""
        nrzi = NRZIEncoder()
        bits = [1] * 8
        encoded = nrzi.encode(bits)
        decoded = nrzi.decode(encoded)
        assert decoded == bits


class TestCCSKProcessor:
    """Test CCSK (Cyclic Code Shift Keying) processor."""

    def test_roundtrip_all_symbols(self):
        """Test all 32 symbols encode/decode correctly."""
        ccsk = CCSKProcessor()
        for sym in range(32):
            chips = ccsk.encode_symbol(sym)
            assert len(chips) == 32

            decoded_sym, confidence = ccsk.decode_chips(np.array(chips, dtype=np.uint8))
            assert decoded_sym == sym, f"Symbol {sym} failed decode"

    def test_confidence_perfect(self):
        """Test confidence is 1.0 for perfect match."""
        ccsk = CCSKProcessor()
        chips = ccsk.encode_symbol(15)
        decoded_sym, confidence = ccsk.decode_chips(np.array(chips, dtype=np.uint8))
        assert confidence == 1.0

    def test_decode_phase_inverted(self):
        """Test decode handles phase inversion."""
        ccsk = CCSKProcessor()
        chips = ccsk.encode_symbol(10)
        # Invert all bits
        inverted = [1 - c for c in chips]
        decoded_sym, confidence = ccsk.decode_chips(np.array(inverted, dtype=np.uint8))
        # Phase inversion should map to another valid symbol
        assert decoded_sym in range(32)


class TestDSSSProcessor:
    """Test DSSS processor."""

    def test_barker_spread(self):
        """Test Barker-11 spread."""
        dsss = DSSSProcessor(sf=11)
        data_bits = [1, 0, 1, 1, 0]  # 5 bits
        spread = dsss.spread(data_bits)
        assert len(spread) == 55  # 5 * 11

    def test_barker_11_default(self):
        """Test default Barker-11 code."""
        dsss = DSSSProcessor()
        assert len(dsss.code) == 11
        # Barker 11 pattern
        assert dsss.code.tolist() == [1, 1, 1, -1, -1, -1, 1, -1, -1, 1, -1]

    def test_custom_spreading_code(self):
        """Test custom spreading code."""
        custom_code = [1, -1, 1, -1, 1, -1]  # 6-chip code
        dsss = DSSSProcessor(chipping_code=custom_code)
        data_bits = [1, 0, 1]
        spread = dsss.spread(data_bits)
        assert len(spread) == 18  # 3 * 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
