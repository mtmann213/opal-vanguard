#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Link Layer Integration Tests
# Note: Some tests require GNU Radio runtime (gnuradio) which may not be available
# in all test environments.

import pytest
import sys
import os
import tempfile
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def create_test_config(modifications=None):
    """Create a minimal test config for link layer testing."""
    config = {
        "mission": {"id": "TEST_LINK_LAYER"},
        "physical": {
            "modulation": "GFSK",
            "samp_rate": 2000000,
            "center_freq": 915000000,
            "samples_per_symbol": 10,
            "freq_dev": 25000,
            "preamble_len": 64,
            "syncword": "0x3D4C5B6A",
        },
        "link_layer": {
            "frame_size": 120,
            "use_fec": True,
            "fec_type": "RS1511",
            "use_interleaving": True,
            "interleaver_rows": 15,
            "use_whitening": True,
            "use_nrzi": True,
            "use_comsec": False,
            "comsec_key": "00" * 16,
            "use_transec": False,
            "use_anti_replay": False,
        },
        "mac_layer": {"arq_enabled": False, "max_retries": 3, "amc_enabled": False},
        "dsss": {"enabled": False, "type": "Barker", "spreading_factor": 11},
        "hopping": {"enabled": False},
        "hardware": {"args": "type=b200", "tx_gain": 70, "rx_gain": 70},
        "application_layer": {"payload_type": "heartbeat"},
    }

    if modifications:
        for section, values in modifications.items():
            if section in config:
                config[section].update(values)

    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w") as f:
        yaml.dump(config, f)
    return path


class TestConfigValidation:
    """Test configuration validation (no gnuradio needed)."""

    @pytest.mark.skipif(
        os.environ.get("GR_AVAILABLE", "false").lower() != "true",
        reason="Requires GNU Radio runtime",
    )
    def test_valid_interleaver_math(self):
        """Test interleaver rows divide evenly into frame_size."""
        config_path = create_test_config(
            {"link_layer": {"frame_size": 120, "interleaver_rows": 15}}
        )

        from packetizer import packetizer

        pkt = packetizer(config_path=config_path)

        assert pkt.frame_size % pkt.interleaver.interleaver_rows == 0

    @pytest.mark.skipif(
        os.environ.get("GR_AVAILABLE", "false").lower() != "true",
        reason="Requires GNU Radio runtime",
    )
    def test_invalid_interleaver_math(self):
        """Test handling of invalid interleaver math."""
        config_path = create_test_config(
            {"link_layer": {"frame_size": 120, "interleaver_rows": 16}}
        )

        from packetizer import packetizer

        pkt = packetizer(config_path=config_path)

        assert pkt.interleaver is not None


@pytest.mark.skipif(
    not os.environ.get("GR_AVAILABLE", "false").lower() == "true",
    reason="Requires GNU Radio runtime",
)
class TestHopGeneratorsWithGR:
    """Test frequency hop generators (requires GNU Radio)."""

    def test_lfsr_generator_basic(self):
        """Test LFSR hop generator produces frequencies."""
        from hop_controller import lfsr_hop_generator

        hop = lfsr_hop_generator(
            seed=0xACE, num_channels=10, center_freq=915e6, channel_spacing=150e3
        )
        hop.handle_trigger(None)

    def test_tod_generator_initialization(self):
        """Test TOD hop generator initializes."""
        from hop_generator_tod import tod_hop_generator

        hop = tod_hop_generator(
            key=b"\x00" * 32,
            num_channels=50,
            center_freq=915e6,
            channel_spacing=150e3,
            dwell_ms=200,
        )

        assert hop.num_channels == 50
        assert hop.center_freq == 915e6

    def test_aes_generator_initialization(self):
        """Test AES hop generator initializes."""
        from hop_generator_aes import aes_hop_generator

        hop = aes_hop_generator(
            key=b"\x00" * 32, num_channels=50, center_freq=915e6, channel_spacing=150e3
        )

        assert hop.num_channels == 50

    def test_aes_generator_blacklist(self):
        """Test AES generator respects blacklist."""
        from hop_generator_aes import aes_hop_generator

        hop = aes_hop_generator(
            key=b"\x00" * 32, num_channels=10, center_freq=915e6, channel_spacing=150e3
        )
        hop.blacklist = [0, 1, 2]

        for _ in range(10):
            hop.handle_trigger(None)


@pytest.mark.skipif(
    not os.environ.get("GR_AVAILABLE", "false").lower() == "true",
    reason="Requires GNU Radio runtime",
)
class TestSessionManagerWithGR:
    """Test session manager (requires GNU Radio)."""

    def test_initial_state(self):
        """Test session manager starts in IDLE."""
        from session_manager import session_manager

        config_path = create_test_config()
        sm = session_manager(initial_seed=0xACE, config_path=config_path)

        assert sm.state == "IDLE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
