#!/usr/bin/env python3
"""
Updated AFSK Receiver - Adjusted parameters for more accurate decoding
"""

import numpy as np
import pyaudio
import time
from scipy.signal import butter, lfilter

MARK_FREQ = 1200  # Hz (Binary 1)
SPACE_FREQ = 2200  # Hz (Binary 0)
BAUD_RATE = 300  # Baud rate
SAMPLE_RATE = 44100  # Hz
NOISE_THRESHOLD = 0.1  # Slightly increased to reduce false positives
CHUNK = 4410  # 0.1 seconds of audio at 44.1kHz

p = pyaudio.PyAudio()

def bandpass_filter(data, center_freq, bandwidth=80):
    """Apply a bandpass filter around the target frequency."""
    nyquist = 0.5 * SAMPLE_RATE
    low = (center_freq - bandwidth / 2) / nyquist
    high = (center_freq + bandwidth / 2) / nyquist
    b, a = butter(4, [low, high], btype='band')
    return lfilter(b, a, data)

def detect_signal(audio_buffer):
    """Detect if a valid signal is present in the audio buffer."""
    mark_filtered = bandpass_filter(audio_buffer, MARK_FREQ)
    space_filtered = bandpass_filter(audio_buffer, SPACE_FREQ)
    mark_energy = np.mean(mark_filtered ** 2)
    space_energy = np.mean(space_filtered ** 2)
    total_energy = mark_energy + space_energy
    return total_energy > NOISE_THRESHOLD

def decode_afsk(audio_buffer):
    """Decode AFSK signal to binary data"""
    samples_per_bit = int(SAMPLE_RATE / BAUD_RATE)
    mark_filtered = bandpass_filter(audio_buffer, MARK_FREQ)
    space_filtered = bandpass_filter(audio_buffer, SPACE_FREQ)
    num_bits = len(audio_buffer) // samples_per_bit
    binary_data = ""
    for i in range(num_bits):
        start = i * samples_per_bit
        end = start + samples_per_bit
        mark_energy = np.sum(mark_filtered[start:end] ** 2)
        space_energy = np.sum(space_filtered[start:end] ** 2)
        binary_data += "1" if mark_energy > space_energy else "0"
    return binary_data

def binary_to_text(binary_data):
    """Convert binary string to text"""
    # Make sure length is multiple of 8
    binary_data = binary_data[:len(binary_data) - (len(binary_data) % 8)]
    text = ""
    for i in range(0, len(binary_data), 8):
        byte = binary_data[i:i+8]
        try:
            text += chr(int(byte, 2))
        except ValueError:
            text += "?"
    return text

def process_audio(data, audio_buffer, in_signal, signal_start_time):
    """Process incoming audio data for AFSK signals"""
    if not in_signal and detect_signal(data):
        in_signal = True
        signal_start_time = time.time()
        audio_buffer = []
        print("Signal detected - receiving...")
    if in_signal:
        audio_buffer.extend(data)
        if not detect_signal(data):
            signal_duration = time.time() - signal_start_time
            if signal_duration >= 0.5:
                print(f"Signal received: {signal_duration:.1f} seconds")
                binary_data = decode_afsk(np.array(audio_buffer))
                print(f"Binary data length: {len(binary_data)} bits")
                print(f"Binary: {binary_data}")
                text = binary_to_text(binary_data)
                print(f"Decoded message: {text}")
                print("-" * 40)
            in_signal = False
            audio_buffer = []
    return audio_buffer, in_signal, signal_start_time

def receive_audio():
    """Main function to receive and process audio."""
    audio_buffer = []
    in_signal = False
    signal_start_time = 0
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    print("Listening for AFSK signal...")
    print(f"MARK: {MARK_FREQ} Hz, SPACE: {SPACE_FREQ} Hz, RATE: {BAUD_RATE} baud")
    try:
        while True:
            data = np.frombuffer(stream.read(CHUNK), dtype=np.int16).astype(np.float32) / 32768.0
            audio_buffer, in_signal, signal_start_time = process_audio(data, audio_buffer, in_signal, signal_start_time)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    receive_audio()
