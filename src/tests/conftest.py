#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Pytest Configuration and Fixtures

import os
import sys
import tempfile
import yaml
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


MISSION_CONFIGS = [
    "level0_test.yaml",
    "level1_soft_link.yaml",
    "level2_repairable.yaml",
    "level3_resilient.yaml",
    "level4_stealth.yaml",
    "level5_blackout.yaml",
    "level6_link16.yaml",
    "level7_ofdm_master.yaml",
    "level8_advanced.yaml",
    "level9_deep_shadow.yaml",
]


@pytest.fixture(scope="session")
def mission_config_path():
    """Return path to mission_configs directory."""
    return os.path.join(os.path.dirname(__file__), "..", "..", "mission_configs")


@pytest.fixture
def all_configs(mission_config_path):
    """Load all mission configurations."""
    configs = {}
    for name in MISSION_CONFIGS:
        path = os.path.join(mission_config_path, name)
        if os.path.exists(path):
            with open(path, "r") as f:
                configs[name] = yaml.safe_load(f)
    return configs


@pytest.fixture
def temp_config(all_configs):
    """Create temporary config for testing."""

    def _create_temp_config(base_name, overrides=None):
        base = all_configs.get(base_name, {})
        if overrides:
            base = _deep_merge(base, overrides)

        fd, path = tempfile.mkstemp(suffix=".yaml")
        with os.fdopen(fd, "w") as f:
            yaml.dump(base, f)
        return path

    return _create_temp_config


def _deep_merge(base, override):
    """Deep merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@pytest.fixture
def level1_config(mission_config_path):
    """Load level1 config for testing."""
    path = os.path.join(mission_config_path, "level1_soft_link.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture
def level6_config(mission_config_path):
    """Load level6 (Link-16) config for testing."""
    path = os.path.join(mission_config_path, "level6_link16.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture
def level5_config(mission_config_path):
    """Load level5 (blackout - with COMSEC and FHSS) config for testing."""
    path = os.path.join(mission_config_path, "level5_blackout.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)
