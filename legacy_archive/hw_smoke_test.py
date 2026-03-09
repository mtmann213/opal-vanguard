#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - Hardware Smoke Test
# Verifies RF path between two USRPs with a simple tone.

import sys
import argparse
import os
from gnuradio import gr, blocks, analog, uhd, qtgui, fft
from PyQt5 import Qt
import sip

def main():
    parser = argparse.ArgumentParser(description="USRP RF Smoke Test")
    parser.add_argument("--role", choices=["TX", "RX"], required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--freq", type=float, default=915e6)
    parser.add_argument("--gain", type=float, default=60)
    args = parser.parse_args()

    # Environment setup
    images_dir = "/home/tx15/install/sdr/share/uhd/images/"
    if os.path.isdir(images_dir): os.environ["UHD_IMAGES_DIR"] = images_dir

    qapp = Qt.QApplication(sys.argv)
    tb = gr.top_block(f"Smoke Test - {args.role}")

    uhd_args = f"type=b200,serial={args.serial}"
    samp_rate = 2e6

    if args.role == "TX":
        print(f"[*] Starting TX Tone at {args.freq/1e6} MHz on USRP {args.serial}")
        src = analog.sig_source_c(samp_rate, analog.GR_COS_WAVE, 1000, 0.5) # 1kHz tone
        sink = uhd.usrp_sink(uhd_args, uhd.stream_args(cpu_format="fc32", channels=[0]))
        sink.set_samp_rate(samp_rate)
        sink.set_center_freq(args.freq, 0)
        sink.set_gain(args.gain, 0)
        sink.set_antenna("TX/RX", 0)
        tb.connect(src, sink)
    else:
        print(f"[*] Starting RX Monitor at {args.freq/1e6} MHz on USRP {args.serial}")
        source = uhd.usrp_source(uhd_args, uhd.stream_args(cpu_format="fc32", channels=[0]))
        source.set_samp_rate(samp_rate)
        source.set_center_freq(args.freq, 0)
        source.set_gain(args.gain, 0)
        source.set_antenna("TX/RX", 0)
        
        snk = qtgui.freq_sink_c(1024, fft.window.WIN_BLACKMAN_HARRIS, args.freq, samp_rate, "RX Spectrum", 1)
        container = sip.wrapinstance(snk.qwidget(), Qt.QWidget)
        container.show()
        tb.connect(source, snk)

    tb.start()
    print("[!] Running. Close the GUI or press Ctrl+C to stop.")
    qapp.exec_()
    tb.stop()
    tb.wait()

if __name__ == "__main__":
    main()
