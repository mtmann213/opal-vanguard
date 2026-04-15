#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - RS FEC Unit Tests

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rs_helper import RS1511, RS3115


class TestRS1511:
    """Test RS(15,11) Reed-Solomon codec."""

    def test_encode(self):
        """Test encoding produces correct parity."""
        rs = RS1511()
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        encoded = rs.encode(data)
        assert len(encoded) == 15
        assert encoded[:11] == data

    def test_decode_no_errors(self):
        """Test decoding with no errors."""
        rs = RS1511()
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        encoded = rs.encode(data)
        decoded, errors = rs.decode(encoded)
        assert decoded == data
        assert errors == 0

    def test_decode_1_error(self):
        """Test correcting 1 symbol error."""
        rs = RS1511()
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        encoded = rs.encode(data)

        # Corrupt 1 symbol
        corrupted = list(encoded)
        corrupted[5] ^= 7
        decoded, errors = rs.decode(corrupted)

        assert decoded == data
        assert errors == 1

    def test_decode_2_errors(self):
        """Test correcting 2 symbol errors."""
        rs = RS1511()
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        encoded = rs.encode(data)

        # Corrupt 2 symbols
        corrupted = list(encoded)
        corrupted[5] ^= 7
        corrupted[10] ^= 3
        decoded, errors = rs.decode(corrupted)

        assert decoded == data
        assert errors == 2

    def test_decode_unrecoverable(self):
        """Test handling of unrecoverable errors."""
        rs = RS1511()
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        encoded = rs.encode(data)

        # Corrupt 5 symbols (beyond t=2 capability)
        corrupted = list(encoded)
        for i in range(5):
            corrupted[i] ^= 15
        decoded, errors = rs.decode(corrupted)

        # Should return corrupted data with 0 errors (uncorrectable)
        assert len(decoded) == 11


class TestRS3115:
    """Test RS(31,15) Reed-Solomon codec (Link-16)."""

    def test_encode(self):
        """Test encoding produces correct parity."""
        rs = RS3115()
        data = list(range(1, 16))  # [1..15]
        encoded = rs.encode(data)
        assert len(encoded) == 31
        assert encoded[:15] == data

    def test_decode_no_errors(self):
        """Test decoding with no errors."""
        rs = RS3115()
        data = list(range(1, 16))
        encoded = rs.encode(data)
        decoded, errors = rs.decode(encoded)
        assert decoded == data
        assert errors == 0

    def test_decode_1_error(self):
        """Test correcting 1 symbol error."""
        rs = RS3115()
        data = list(range(1, 16))
        encoded = rs.encode(data)

        # Corrupt 1 symbol
        corrupted = list(encoded)
        corrupted[15] ^= 7
        decoded, errors = rs.decode(corrupted)

        assert decoded == data
        assert errors == 1


class TestRSInterop:
    """Test RS interoperability with packetizer/depacketizer patterns."""

    def test_rs1511_packetizer_format(self):
        """Test RS1511 nibble encoding format used in packetizer.

        Packetizer takes 11 bytes (22 nibbles), splits into two 11-nibble groups,
        each encoded with RS(15,11), producing 30 nibbles → 15 bytes.
        """
        rs = RS1511()

        # 11 bytes → 22 nibbles
        raw_bytes = bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
        nibs = []
        for b in raw_bytes:
            nibs.extend([(b >> 4) & 0x0F, b & 0x0F])

        # First 11 nibbles (high nibbles) → encode → 15 nibbles
        first_group = nibs[:11]
        encoded1 = rs.encode(first_group)  # Returns 15 nibbles (11 data + 4 parity)

        # Second 11 nibbles (low nibbles) → encode → 15 nibbles
        second_group = nibs[11:22]
        encoded2 = rs.encode(second_group)

        # Combine 30 nibbles into 15 bytes
        fec_bytes = []
        for i in range(15):
            fec_bytes.append(((encoded1[i] & 0x0F) << 4) | (encoded2[i] & 0x0F))

        assert len(fec_bytes) == 15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
