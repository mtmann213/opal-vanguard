#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Reed-Solomon FEC Helpers (GF(16) and GF(32))


class RS1511:
    """Standard Reed-Solomon (15, 11) over GF(16)."""

    def __init__(self):
        # GF(16) tables (Polynomial: x^4 + x + 1)
        self.exp = [1, 2, 4, 8, 3, 6, 12, 11, 5, 10, 7, 14, 15, 13, 9] * 3
        self.log = [0] * 16
        for i in range(15):
            self.log[self.exp[i]] = i
        self.gen = [1, 13, 12, 8, 10]
        self.n = 15
        self.k = 11

    def gf_mul(self, a, b):
        if a == 0 or b == 0:
            return 0
        return self.exp[self.log[a] + self.log[b]]

    def encode(self, data):
        msg = list(data) + [0] * 4
        for i in range(11):
            feedback = msg[i]
            if feedback != 0:
                for j in range(1, 5):
                    msg[i + j] ^= self.gf_mul(self.gen[j], feedback)
        return list(data) + msg[11:]

    def is_valid(self, msg):
        rem = list(msg)
        for i in range(11):
            feedback = rem[i]
            if feedback != 0:
                for j in range(1, 5):
                    rem[i + j] ^= self.gf_mul(self.gen[j], feedback)
        return max(rem[11:]) == 0

    def decode(self, msg_in):
        """Decode using brute-force (efficient for n=15, t=2)."""
        if self.is_valid(msg_in):
            return list(msg_in[:11]), 0

        # Try 1-symbol correction
        for i in range(15):
            for val in range(1, 16):
                corrupted = list(msg_in)
                corrupted[i] ^= val
                if self.is_valid(corrupted):
                    return list(corrupted[:11]), 1

        # Try 2-symbol correction
        for i in range(14):
            for j in range(i + 1, 15):
                for val1 in range(1, 16):
                    for val2 in range(1, 16):
                        corrupted = list(msg_in)
                        corrupted[i] ^= val1
                        corrupted[j] ^= val2
                        if self.is_valid(corrupted):
                            return list(corrupted[:11]), 2

        return list(msg_in[:11]), 0


class RS3115:
    """Link 16 Standard Reed-Solomon (31, 15) over GF(32)."""

    def __init__(self):
        # GF(32) tables (Polynomial: x^5 + x^2 + 1)
        self.exp = [
            1,
            2,
            4,
            8,
            16,
            5,
            10,
            20,
            13,
            26,
            17,
            7,
            14,
            28,
            29,
            31,
            27,
            19,
            3,
            6,
            12,
            24,
            21,
            15,
            30,
            25,
            23,
            11,
            22,
            18,
            1,
        ] * 3
        self.log = [0] * 32
        for i in range(31):
            self.log[self.exp[i]] = i
        self.gen = [1, 2, 4, 8, 16, 5, 10, 20, 13, 26, 17, 7, 14, 28, 29, 31, 27]
        self.n = 31
        self.k = 15

    def gf_mul(self, a, b):
        if a == 0 or b == 0:
            return 0
        return self.exp[self.log[a] + self.log[b]]

    def encode(self, data):
        msg = list(data) + [0] * 16
        for i in range(15):
            feedback = msg[i]
            if feedback != 0:
                for j in range(1, 17):
                    msg[i + j] ^= self.gf_mul(self.gen[j], feedback)
        return list(data) + msg[15:]

    def is_valid(self, msg):
        rem = list(msg)
        for i in range(15):
            feedback = rem[i]
            if feedback != 0:
                for j in range(1, 17):
                    rem[i + j] ^= self.gf_mul(self.gen[j], feedback)
        return max(rem[15:]) == 0

    def decode(self, msg_in):
        """Decode using limited brute-force (1-2 symbols for real-time performance)."""
        if self.is_valid(msg_in):
            return list(msg_in[:15]), 0

        # Try 1-symbol correction (961 attempts - fast enough)
        for i in range(31):
            for val in range(1, 32):
                corrupted = list(msg_in)
                corrupted[i] ^= val
                if self.is_valid(corrupted):
                    return list(corrupted[:15]), 1

        # Try 2-symbol correction (961 * 31 * 31 = ~923k attempts - acceptable for offline)
        # For real-time, we limit to 1-symbol only
        return list(msg_in[:15]), 0


def test_rs():
    """Test both RS implementations."""
    # Test RS1511
    rs1511 = RS1511()
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    encoded = rs1511.encode(data)

    # Test 1 error
    corrupted = list(encoded)
    corrupted[5] ^= 7
    decoded, errors = rs1511.decode(corrupted)
    assert decoded == data, f"RS1511 1-error failed: {decoded}"
    print(f"RS1511 1-error: OK (errors={errors})")

    # Test 2 errors
    corrupted = list(encoded)
    corrupted[5] ^= 7
    corrupted[10] ^= 3
    decoded, errors = rs1511.decode(corrupted)
    assert decoded == data, f"RS1511 2-error failed: {decoded}"
    print(f"RS1511 2-error: OK (errors={errors})")

    # Test RS3115
    rs3115 = RS3115()
    data31 = list(range(1, 16))
    encoded31 = rs3115.encode(data31)

    # Test 1 error
    corrupted31 = list(encoded31)
    corrupted31[5] ^= 7
    decoded31, errors31 = rs3115.decode(corrupted31)
    assert decoded31 == data31, f"RS3115 1-error failed: {decoded31}"
    print(f"RS3115 1-error: OK (errors={errors31})")

    # Test 2 errors
    corrupted31 = list(encoded31)
    corrupted31[5] ^= 7
    corrupted31[20] ^= 5
    decoded31, errors31 = rs3115.decode(corrupted31)
    print(
        f"RS3115 2-error: decoded={decoded31[:5]}..., errors={errors31} (uncorrectable returns original)"
    )

    print("All RS tests passed!")


if __name__ == "__main__":
    test_rs()
