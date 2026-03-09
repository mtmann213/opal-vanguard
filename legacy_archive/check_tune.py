from gnuradio import uhd
import time

try:
    snk = uhd.usrp_sink("type=b200", uhd.stream_args(cpu_format="fc32", channels=[0]))
    snk.set_center_freq(915000000, 0)
    time.sleep(0.5)
    print("LO Freq: ", snk.get_center_freq(0))
except Exception as e:
    print("Could not init USRP:", e)
