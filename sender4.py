#!/usr/bin/env python3
"""
AFSK Transmitter without VOX
"""

import numpy as np
import pyaudio
import argparse
import time
import sys

MARK_FREQ = 1200  # Hz (Binary 1)
SPACE_FREQ = 2200  # Hz (Binary 0)
BAUD_RATE = 300  # Baud rate
SAMPLE_RATE = 44100  # Hz
AMPLITUDE = 0.95  # High amplitude for reliable transmission

p = pyaudio.PyAudio()

def text_to_binary(text):
    """Convert text to binary string"""
    return ''.join(format(ord(c), '08b') for c in text)

def generate_sync_pattern():
    """Generate sync pattern after VOX preamble"""
    duration = 1.0  # Sync pattern duration
    bit_samples = int(SAMPLE_RATE / BAUD_RATE)
    total_bits = int(duration * BAUD_RATE)
    signal = np.zeros(total_bits * bit_samples, dtype=np.float32)
    for i in range(total_bits):
        freq = MARK_FREQ if i % 2 == 0 else SPACE_FREQ
        t = np.arange(bit_samples) / SAMPLE_RATE
        start = i * bit_samples
        signal[start:start+bit_samples] = AMPLITUDE * np.sin(2 * np.pi * freq * t)
    return signal

def generate_afsk(binary_data):
    """Generate AFSK audio signal from binary data"""
    samples_per_bit = int(SAMPLE_RATE / BAUD_RATE)
    signal = np.zeros(len(binary_data) * samples_per_bit, dtype=np.float32)
    for i, bit in enumerate(binary_data):
        freq = MARK_FREQ if bit == '1' else SPACE_FREQ
        t = np.arange(samples_per_bit) / SAMPLE_RATE
        bit_signal = AMPLITUDE * np.sin(2 * np.pi * freq * t)
        start = i * samples_per_bit
        signal[start:start+samples_per_bit] = bit_signal
    return signal

def transmit(message, repeat=1, delay=2):
    """Transmit a message using AFSK without VOX"""
    binary_data = text_to_binary(message)
    print(f"Message: {message}")
    print(f"Binary: {binary_data}")
    print(f"Length: {len(binary_data)} bits")
    sync_pattern = generate_sync_pattern()
    data_signal = generate_afsk(binary_data)
    signal = np.concatenate([sync_pattern, data_signal])
    audio_data = (signal * 32767).astype(np.int16)
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=SAMPLE_RATE,
                    output=True)
    for i in range(repeat):
        if i > 0:
            print(f"Repeat {i+1}/{repeat} - Waiting {delay} seconds...")
            time.sleep(delay)
        print(f"Transmitting... ({i+1}/{repeat})")
        stream.write(audio_data.tobytes())
        print("Transmission complete!")
    stream.stop_stream()
    stream.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AFSK Transmitter without VOX")
    parser.add_argument("-m", "--message", required=True, help="Message to transmit")
    parser.add_argument("-r", "--repeat", type=int, default=1, help="Number of times to repeat")
    parser.add_argument("-d", "--delay", type=float, default=2, help="Delay between repeats (seconds)")
    args = parser.parse_args()
    try:
        transmit(args.message, args.repeat, args.delay)
    finally:
        p.terminate()
