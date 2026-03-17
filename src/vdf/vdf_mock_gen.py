#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Opal Vanguard - VDF Mock Waveform Generator (v3.1 DSP-Perfect)

import numpy as np
import os
from scipy import signal

def get_rrc_filter(sps, span=10, alpha=0.35):
    """Generates a high-fidelity Root-Raised Cosine filter."""
    n = np.arange(-span*sps, span*sps + 1)
    with np.errstate(divide='ignore', invalid='ignore'):
        h = (np.sin(np.pi * n / sps * (1 - alpha)) +
             4 * alpha * n / sps * np.cos(np.pi * n / sps * (1 + alpha))) / \
            (np.pi * n / sps * (1 - (4 * alpha * n / sps)**2))
        h[len(n)//2] = 1 - alpha + 4 * alpha / np.pi
        idx = np.where(np.abs(1 - (4 * alpha * n / sps)**2) < 1e-9)[0]
        if len(idx) > 0:
            h[idx] = alpha / np.sqrt(2) * ((1+2/np.pi)*np.sin(np.pi/(4*alpha)) + (1-2/np.pi)*np.cos(np.pi/(4*alpha)))
    return h / np.sqrt(np.sum(h**2))

def apply_pilot_tone(data, sample_rate=1e6, duration=0.02):
    """Prepends a 20ms CW Pilot Tone at 100kHz offset (Nuclear Robustness)."""
    num_pilot = int(sample_rate * duration)
    t = np.arange(num_pilot) / sample_rate
    pilot = 1.0 * np.exp(1j * 2 * np.pi * 50e3 * t).astype(np.complex64) # v3.1: Aligned to 50kHz
    silence = np.zeros(5000, dtype=np.complex64)
    return np.concatenate([pilot, silence, data])

def apply_sco_drift(data, ppm=100):
    if ppm == 0: return data
    ratio = 1.0 + (ppm / 1e6)
    up, down = int(1e6 + ppm), int(1e6)
    return signal.resample_poly(data, up, down).astype(np.complex64)

def normalize_name(name):
    return name.lower().replace("-", "_")

# --- MODULATION GENERATORS ---

def gen_psk(m, num_samples=1050000, sps=8):
    num_symbols = num_samples // sps
    bits = np.random.randint(0, m, num_symbols)
    mapping = np.exp(1j * 2 * np.pi * np.arange(m) / m)
    upsampled = np.zeros(num_symbols * sps, dtype=np.complex64)
    upsampled[::sps] = mapping[bits]
    h = get_rrc_filter(sps)
    return np.convolve(upsampled, h, mode='same')[:num_samples]

def gen_oqpsk(num_samples=1050000, sps=8):
    num_symbols = num_samples // sps
    bits = np.random.randint(0, 4, num_symbols)
    mapping = np.array([1+1j, -1+1j, -1-1j, 1-1j]) / np.sqrt(2)
    symbols = mapping[bits]
    # Offset Q channel by half a symbol
    i_chan = np.repeat(np.real(symbols), sps)
    q_chan = np.repeat(np.imag(symbols), sps)
    q_chan = np.roll(q_chan, sps // 2)
    waveform = (i_chan + 1j * q_chan).astype(np.complex64)
    h = get_rrc_filter(sps)
    return np.convolve(waveform, h, mode='same')[:num_samples]

def gen_qam(m, num_samples=1050000, sps=8):
    num_symbols = num_samples // sps
    side = int(np.ceil(np.sqrt(m)))
    points = np.arange(-side+1, side+1, 2)
    mapping = np.array([complex(i, q) for i in points for q in points])[:m]
    mapping /= np.sqrt(np.mean(np.abs(mapping)**2))
    upsampled = np.zeros(num_symbols * sps, dtype=np.complex64)
    upsampled[::sps] = mapping[np.random.randint(0, m, num_symbols)]
    h = get_rrc_filter(sps)
    return np.convolve(upsampled, h, mode='same')[:num_samples]

def gen_apsk(rings, num_samples=1050000, sps=8):
    num_symbols = num_samples // sps
    mapping = []
    for r, n in rings: mapping.extend([r * np.exp(1j * 2 * np.pi * i / n) for i in range(n)])
    mapping = np.array(mapping); mapping /= np.sqrt(np.mean(np.abs(mapping)**2))
    upsampled = np.zeros(num_symbols * sps, dtype=np.complex64)
    upsampled[::sps] = mapping[np.random.randint(0, len(mapping), num_symbols)]
    h = get_rrc_filter(sps)
    return np.convolve(upsampled, h, mode='same')[:num_samples]

def gen_ask(m, num_samples=1050000, sps=8):
    num_symbols = num_samples // sps
    mapping = np.linspace(0.2, 1.0, m).astype(np.complex64)
    upsampled = np.zeros(num_symbols * sps, dtype=np.complex64)
    upsampled[::sps] = mapping[np.random.randint(0, m, num_symbols)]
    h = get_rrc_filter(sps)
    return np.convolve(upsampled, h, mode='same')[:num_samples]

def gen_ook(num_samples=1050000, sps=8):
    num_symbols = num_samples // sps
    mapping = np.array([0.0, 1.0], dtype=np.complex64)
    upsampled = np.zeros(num_symbols * sps, dtype=np.complex64)
    upsampled[::sps] = mapping[np.random.randint(0, 2, num_symbols)]
    h = get_rrc_filter(sps)
    return np.convolve(upsampled, h, mode='same')[:num_samples]

def gen_gmsk(num_samples=1050000, sps=8, bt=0.35):
    bits = np.random.randint(0, 2, num_samples // sps)
    symbols = np.where(bits == 1, 1.0, -1.0)
    t = np.linspace(-2, 2, sps)
    gauss = np.exp(-np.pi * (t / bt)**2); gauss /= np.sum(gauss)
    filtered = np.convolve(np.repeat(symbols, sps), gauss, mode='same')
    phase = np.cumsum(filtered) * (np.pi / 2.0 / sps)
    return np.exp(1j * phase).astype(np.complex64)[:num_samples]

def gen_fm(num_samples=1050000):
    t = np.arange(num_samples)
    message = signal.detrend(np.cumsum(np.random.normal(0, 0.05, num_samples)))
    message /= np.max(np.abs(message))
    return np.exp(1j * 0.5 * message).astype(np.complex64)[:num_samples]

def gen_am(num_samples=1050000, carrier=True, ssb=False):
    t = np.arange(num_samples) / 1e6
    message = 0.5 * np.sin(2 * np.pi * 1000 * t) + 0.5
    if ssb:
        analytic = signal.hilbert(message)
        waveform = analytic if carrier else analytic - np.mean(analytic)
    else:
        waveform = (message + 1.0) if carrier else message
    return waveform.astype(np.complex64)[:num_samples]

def main():
    os.makedirs("data/vdf_mock", exist_ok=True)
    mods = [
        ('32PSK', lambda: gen_psk(32)),
        ('16APSK', lambda: gen_apsk([(1.0, 4), (2.5, 12)])),
        ('32QAM', lambda: gen_qam(32)),
        ('FM', gen_fm),
        ('GMSK', gen_gmsk),
        ('32APSK', lambda: gen_apsk([(1.0, 4), (2.5, 12), (4.0, 16)])),
        ('OQPSK', gen_oqpsk),
        ('8ASK', lambda: gen_ask(8)),
        ('BPSK', lambda: gen_psk(2)),
        ('8PSK', lambda: gen_psk(8)),
        ('AM-SSB-SC', lambda: gen_am(carrier=False, ssb=True)),
        ('4ASK', lambda: gen_ask(4)),
        ('16PSK', lambda: gen_psk(16)),
        ('64APSK', lambda: gen_apsk([(1.0, 4), (2.0, 12), (3.0, 16), (4.0, 32)])),
        ('128QAM', lambda: gen_qam(128)),
        ('128APSK', lambda: gen_apsk([(1.0, 4), (2.0, 12), (3.0, 16), (4.0, 32), (5.0, 64)])),
        ('AM-DSB-SC', lambda: gen_am(carrier=False, ssb=False)),
        ('AM-SSB-WC', lambda: gen_am(carrier=True, ssb=True)),
        ('64QAM', lambda: gen_qam(64)),
        ('QPSK', lambda: gen_psk(4)),
        ('256QAM', lambda: gen_qam(256)),
        ('AM-DSB-WC', lambda: gen_am(carrier=True, ssb=False)),
        ('OOK', gen_ook),
        ('16QAM', lambda: gen_qam(16))
    ]
    for name, func in mods:
        safe_name = normalize_name(name)
        print(f"[VDF] Archiving {name} ({safe_name})...")
        raw_data = func()
        # Safety normalization
        raw_data = 0.8 * raw_data / (np.max(np.abs(raw_data)) + 1e-9)
        final_wave = apply_pilot_tone(raw_data)
        np.save(f"data/vdf_mock/{safe_name}_pilot.npy", final_wave)
    print(f"[VDF] v3.1 DSP-Perfect Archive complete.")

if __name__ == "__main__": main()
