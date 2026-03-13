#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Mission Simulation Automator (Hardware Only)

import subprocess
import time
import sys
import os
import argparse
import fcntl

def set_non_blocking(file_obj):
    fd = file_obj.fileno()
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

def run_hardware_test(config_path, alpha_serial, bravo_serial, duration=60):
    print(f"\n" + "="*60)
    print(f"🚀 STARTING HARDWARE TEST: {os.path.basename(config_path)}")
    print(f"📡 ALPHA: {alpha_serial} | BRAVO: {bravo_serial}")
    print("="*60)

    env = os.environ.copy()
    env["PYTHONPATH"] = env.get("PYTHONPATH", "") + ":" + os.path.join(os.getcwd(), "src")

    # Headless commands for efficiency
    cmd_alpha = ["sudo", "-E", "python3", "src/usrp_headless.py", "--role", "ALPHA", "--config", config_path, "--serial", alpha_serial]
    cmd_bravo = ["sudo", "-E", "python3", "src/usrp_headless.py", "--role", "BRAVO", "--config", config_path, "--serial", bravo_serial]

    print(f"[*] Launching BRAVO...")
    p_bravo = subprocess.Popen(cmd_bravo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    time.sleep(2) 
    print(f"[*] Launching ALPHA...")
    p_alpha = subprocess.Popen(cmd_alpha, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)

    set_non_blocking(p_alpha.stdout)
    set_non_blocking(p_bravo.stdout)

    start_time = time.time()
    alpha_rx, bravo_rx = False, False

    try:
        while time.time() - start_time < duration:
            for p, name, status in [(p_alpha, "ALPHA", alpha_rx), (p_bravo, "BRAVO", bravo_rx)]:
                try:
                    out = p.stdout.read(4096)
                    if out:
                        for line in out.splitlines():
                            print(f"  [{name}] {line.strip()}")
                            if "RX DATA:" in line:
                                if name == "ALPHA": alpha_rx = True
                                else: bravo_rx = True
                except: pass

            if alpha_rx and bravo_rx:
                print("\n✅ SUCCESS: Bidirectional Hardware Link Verified!")
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[!] Aborted by user.")
    finally:
        print("\n[*] Cleaning up processes...")
        for p in [p_alpha, p_bravo]:
            p.terminate()
            try: p.wait(timeout=2)
            except: p.kill()

    return alpha_rx and bravo_rx

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="mission_configs/level1_soft_link.yaml")
    parser.add_argument("--alpha", default="3449AC1")
    parser.add_argument("--bravo", default="3457464")
    parser.add_argument("--duration", type=int, default=60)
    args = parser.parse_args()

    success = run_hardware_test(args.config, args.alpha, args.bravo, args.duration)
    sys.exit(0 if success else 1)
