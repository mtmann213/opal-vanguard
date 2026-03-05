#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Configuration Validator

import os
import yaml

def validate_config(config_path):
    """Checks if the provided YAML config is physically and logically viable."""
    if not os.path.exists(config_path):
        return False, f"Config file not found: {config_path}"

    try:
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        return False, f"Failed to parse YAML: {e}"

    # 1. Hardware Constraints
    hw = cfg.get('hardware', {})
    samp_rate = hw.get('samp_rate', 0)
    if samp_rate < 1e6 or samp_rate > 56e6:
        return False, f"Sample rate {samp_rate} is outside stable USRP B205/B210 limits (1M-56M)."

    # 2. Hopping vs Tuning Latency
    hop = cfg.get('hopping', {})
    if hop.get('enabled', False):
        dwell = hop.get('dwell_time_ms', 0)
        lookahead = hop.get('lookahead_ms', 0)
        if dwell < 10:
            return False, f"Dwell time {dwell}ms is too fast for software-timed UHD tuning (min 10ms)."
        if lookahead >= dwell:
            return False, f"Lookahead ({lookahead}ms) must be smaller than dwell time ({dwell}ms)."

    # 3. Link Layer Consistency
    link = cfg.get('link_layer', {})
    interleaving = link.get('use_interleaving', False)
    rows = link.get('interleaver_rows', 0)
    if interleaving and (rows < 2 or rows > 64):
        return False, f"Interleaver rows ({rows}) should be between 2 and 64 for stability."

    # 4. Mission Specifics (Level 6 / Link-16)
    mission_id = cfg.get('mission', {}).get('id', "")
    if "LEVEL_6" in mission_id or "LINK-16" in mission_id:
        dsss_type = cfg.get('dsss', {}).get('type', "")
        if dsss_type != "CCSK":
            print("WARNING: Link-16 mode detected but CCSK is not enabled. Authenticity will be reduced.")

    return True, "Configuration Validated Successfully."

if __name__ == "__main__":
    # Self-test
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "mission_configs/level1_soft_link.yaml"
    success, msg = validate_config(path)
    print(f"[{'PASS' if success else 'FAIL'}] {msg}")
