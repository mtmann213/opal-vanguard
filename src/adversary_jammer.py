#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Red Team "Adversary" Jammer (USRP B210/B205mini)

import sys
import numpy as np
from gnuradio import gr, blocks, analog, uhd, filter
import argparse
import os

def main():
    parser = argparse.ArgumentParser(description="Opal Vanguard Red Team Jammer")
    parser.add_argument("--serial", default="", help="Serial number of the Red Team USRP")
    parser.add_argument("--freq", type=float, default=915e6, help="Center Frequency (Hz)")
    parser.add_argument("--rate", type=float, default=2e6, help="Sample Rate (Hz)")
    parser.add_argument("--gain", type=float, default=70, help="TX Gain (0-90 dB)")
    parser.add_argument("--mode", choices=["NOISE", "SWEEP", "PULSE"], default="NOISE", help="Jamming Mode")
    parser.add_argument("--sweep-rate", type=float, default=10.0, help="Sweep frequency (Hz)")
    parser.add_argument("--pulse-ms", type=float, default=100.0, help="Pulse dwell time (ms)")
    args = parser.parse_args()

    tb = gr.top_block("Opal Vanguard Red Team Jammer")

    # USRP Sink
    uhd_args = "type=b200"
    if args.serial: uhd_args += f",serial={args.serial}"
    
    # Try to find images directory automatically
    images_dir = "/home/tx15/install/sdr/share/uhd/images/"
    if os.path.isdir(images_dir): os.environ["UHD_IMAGES_DIR"] = images_dir
    
    try:
        sink = uhd.usrp_sink(uhd_args, uhd.stream_args(cpu_format="fc32", channels=[0]))
        sink.set_samp_rate(args.rate)
        sink.set_center_freq(args.freq, 0)
        sink.set_gain(args.gain, 0)
        sink.set_antenna("TX/RX", 0)
    except Exception as e:
        print(f"FATAL: USRP ERROR: {e}"); sys.exit(1)

    # 1. Noise Source (Broadband DoS)
    noise = analog.noise_source_c(analog.GR_GAUSSIAN, 1.0)

    # 2. Swept Tone (Scanning Jammer)
    sweep_gen = analog.sig_source_c(args.rate, analog.GR_COS_WAVE, 0, 1.0)
    sweep_ctrl = analog.sig_source_f(args.rate, analog.GR_SAW_WAVE, args.sweep_rate, args.rate/4)
    vco = blocks.vco_c(args.rate, 2 * np.pi, 1.0)
    
    # 3. Pulsed Jammer (Intermittent DoS)
    pulse_gen = analog.sig_source_f(args.rate, analog.GR_SQR_WAVE, 1000.0/args.pulse_ms, 1.0)
    mult = blocks.multiply_vcc(1)

    if args.mode == "NOISE":
        tb.connect(noise, sink)
        print(f"[*] MODE: Broadband NOISE at {args.gain}dB Gain")
    elif args.mode == "SWEEP":
        tb.connect(sweep_ctrl, vco, sink)
        print(f"[*] MODE: Swept-Frequency Jammer (Rate: {args.sweep_rate}Hz)")
    elif args.mode == "PULSE":
        # Combine noise and pulse
        f2c = blocks.float_to_complex(1)
        tb.connect(pulse_gen, f2c)
        tb.connect(noise, (mult, 0))
        tb.connect(f2c, (mult, 1))
        tb.connect(mult, sink)
        print(f"[*] MODE: Pulsed NOISE Jammer (Dwell: {args.pulse_ms}ms)")

    print(f"[*] TARGET: {args.freq/1e6:.2f} MHz @ {args.rate/1e6:.2f} Msps")
    print("[!] CTRL+C to stop jamming.")
    
    tb.start()
    try:
        input("Press Enter to stop jamming...\n")
    except EOFError:
        pass
    tb.stop()
    tb.wait()

if __name__ == '__main__':
    main()
