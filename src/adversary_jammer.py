#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Red Team "Adversary" Jammer (USRP B210/B205mini)

import sys
import numpy as np
from gnuradio import gr, blocks, analog, uhd, filter
import argparse
import os
import time
import json

def main():
    parser = argparse.ArgumentParser(description="Opal Vanguard Red Team Jammer")
    parser.add_argument("--serial", default="", help="Serial number of the Red Team USRP")
    parser.add_argument("--freq", type=float, default=915e6, help="Center Frequency (Hz)")
    parser.add_argument("--rate", type=float, default=2e6, help="Sample Rate (Hz)")
    parser.add_argument("--gain", type=float, default=70, help="TX Gain (0-90 dB)")
    parser.add_argument("--mode", choices=["NOISE", "SWEEP", "PULSE", "FOLLOWER"], default="NOISE", help="Jamming Mode")
    parser.add_argument("--sweep-rate", type=float, default=10.0, help="Sweep frequency (Hz)")
    parser.add_argument("--pulse-ms", type=float, default=100.0, help="Pulse dwell time (ms)")
    parser.add_argument("--log-telemetry", action="store_true", help="Log Target Locks to JSONL")
    args = parser.parse_args()

    tb = gr.top_block("Opal Vanguard Red Team Jammer")
    
    # Telemetry
    telemetry_file = None
    if args.log_telemetry:
        telemetry_file = open("jammer_telemetry.jsonl", "a")
        telemetry_file.write(json.dumps({"timestamp": time.time(), "event": "JAMMER_START", "mode": args.mode}) + "\n")
        telemetry_file.flush()

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
    elif args.mode == "FOLLOWER":
        try:
            source = uhd.usrp_source(uhd_args, uhd.stream_args(cpu_format="fc32", channels=[0]))
            source.set_samp_rate(args.rate)
            source.set_center_freq(args.freq, 0)
            source.set_gain(args.gain, 0)
            source.set_antenna("TX/RX", 0)
        except Exception as e:
            print(f"FATAL: USRP RX ERROR: {e}"); sys.exit(1)
            
        tb.sig_gen = analog.sig_source_c(args.rate, analog.GR_COS_WAVE, 0, 1.0)
        tb.multiplier = blocks.multiply_const_cc(0.0)
        tb.pulse_ms = args.pulse_ms
        
        fft_size = 1024
        s2v = blocks.stream_to_vector(gr.sizeof_gr_complex, fft_size)
        
        class FollowerLogic(gr.sync_block):
            def __init__(self, samp_rate, fft_size, parent, telemetry_file=None):
                gr.sync_block.__init__(self, name="FollowerLogic", in_sig=[(np.complex64, fft_size)], out_sig=None)
                self.samp_rate = samp_rate
                self.fft_size = fft_size
                self.parent = parent
                self.state = "LOOKING"
                self.timer = 0
                self.skip = 0
                self.telemetry_file = telemetry_file
                
            def work(self, input_items, output_items):
                for vec in input_items[0]:
                    if self.state == "JAMMING":
                        self.timer -= 1
                        if self.timer <= 0:
                            self.parent.multiplier.set_k(0.0)
                            self.state = "FLUSHING"
                            self.timer = 10
                    elif self.state == "FLUSHING":
                        self.timer -= 1
                        if self.timer <= 0:
                            self.state = "LOOKING"
                    elif self.state == "LOOKING":
                        self.skip += 1
                        if self.skip % 2 != 0: continue
                        
                        spectrum = np.fft.fftshift(np.fft.fft(vec))
                        power = np.abs(spectrum)**2
                        max_idx = np.argmax(power)
                        max_pwr = power[max_idx]
                        avg_pwr = np.mean(power)
                        
                        if max_pwr > avg_pwr * 15 and max_pwr > 0.5:
                            offset_hz = (max_idx - self.fft_size / 2) * (self.samp_rate / self.fft_size)
                            target_freq = args.freq + offset_hz
                            print(f"\033[91m[FOLLOWER] Target Lock: {target_freq/1e6:.3f} MHz\033[0m")
                            self.parent.sig_gen.set_frequency(offset_hz)
                            self.parent.multiplier.set_k(1.0)
                            self.state = "JAMMING"
                            self.timer = int((self.parent.pulse_ms / 1000.0) * (self.samp_rate / self.fft_size))
                            
                            if self.telemetry_file:
                                self.telemetry_file.write(json.dumps({"timestamp": time.time(), "event": "TARGET_LOCK", "freq_hz": target_freq}) + "\n")
                                self.telemetry_file.flush()
                return len(input_items[0])
                
        follower = FollowerLogic(args.rate, fft_size, tb, telemetry_file)
        tb.connect(source, s2v, follower)
        tb.connect(tb.sig_gen, tb.multiplier, sink)
        print(f"[*] MODE: Autonomous Follower Jammer (Dwell: {args.pulse_ms}ms)")

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
