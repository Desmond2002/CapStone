#!/usr/bin/env python3
"""
VOX-Optimized AFSK Transmitter
"""

import numpy as np
import pyaudio
import argparse
import time
import sys

# AFSK parameters
MARK_FREQ = 1200  # Hz (Binary 1)
SPACE_FREQ = 2200 # Hz (Binary 0)
BAUD_RATE = 300   # Lower baud rate for better reliability
SAMPLE_RATE = 44100 # Hz
AMPLITUDE = 0.95  # High amplitude for reliable VOX triggering

# VOX optimizations
VOX_PREAMBLE_DURATION = 1.5  # seconds (longer to ensure VOX triggers)
VOX_POSTAMBLE_DURATION = 0.5  # seconds (keep VOX open until message completes)

# Create audio object
p = pyaudio.PyAudio()

def text_to_binary(text):
    """Convert text to binary string"""
    return ''.join(format(ord(c), '08b') for c in text)

def generate_vox_preamble():
    """Generate a steady tone to trigger VOX"""
    duration = VOX_PREAMBLE_DURATION
    samples = int(duration * SAMPLE_RATE)
    
    # Use steady mark frequency for reliable VOX activation
    t = np.arange(samples) / SAMPLE_RATE
    preamble = AMPLITUDE * np.sin(2 * np.pi * MARK_FREQ * t)
    
    # Add fade-in for smoother start
    fade_in = min(int(0.05 * SAMPLE_RATE), samples)
    preamble[:fade_in] *= np.linspace(0, 1, fade_in)
    
    return preamble

def generate_sync_pattern():
    """Generate sync pattern after VOX preamble"""
    # Alternating pattern (10101010) for better sync
    duration = 0.5  # half second
    bit_samples = int(SAMPLE_RATE / BAUD_RATE)
    total_bits = int(duration * BAUD_RATE)
    
    signal = np.zeros(total_bits * bit_samples, dtype=np.float32)
    
    for i in range(total_bits):
        freq = MARK_FREQ if i % 2 == 0 else SPACE_FREQ
        t = np.arange(bit_samples) / SAMPLE_RATE
        start = i * bit_samples
        signal[start:start+bit_samples] = AMPLITUDE * np.sin(2 * np.pi * freq * t)
    
    return signal

def generate_postamble():
    """Generate trailing tone to keep VOX open until end"""
    duration = VOX_POSTAMBLE_DURATION
    samples = int(duration * SAMPLE_RATE)
    
    t = np.arange(samples) / SAMPLE_RATE
    signal = AMPLITUDE * np.sin(2 * np.pi * MARK_FREQ * t)
    
    # Add fade-out for smoother end
    fade_out = min(int(0.05 * SAMPLE_RATE), samples)
    signal[-fade_out:] *= np.linspace(1, 0, fade_out)
    
    return signal

def generate_afsk(binary_data):
    """Generate AFSK audio signal from binary data"""
    # Calculate samples per bit
    bit_duration = 1.0 / BAUD_RATE
    samples_per_bit = int(SAMPLE_RATE * bit_duration)
    
    # Generate signal
    signal = np.zeros(len(binary_data) * samples_per_bit, dtype=np.float32)
    
    for i, bit in enumerate(binary_data):
        # Select frequency based on bit value
        freq = MARK_FREQ if bit == '1' else SPACE_FREQ
        
        # Generate sine wave for this bit
        t = np.arange(samples_per_bit) / SAMPLE_RATE
        bit_signal = AMPLITUDE * np.sin(2 * np.pi * freq * t)
        
        # Add to main signal
        start = i * samples_per_bit
        signal[start:start+samples_per_bit] = bit_signal
    
    return signal

def transmit(message, repeat=1, delay=2):
    """Transmit a message using AFSK with VOX optimizations"""
    binary_data = text_to_binary(message)
    
    print(f"Message: {message}")
    print(f"Binary: {binary_data}")
    print(f"Length: {len(binary_data)} bits")
    
    # Generate signal components
    vox_preamble = generate_vox_preamble()
    sync_pattern = generate_sync_pattern()
    data_signal = generate_afsk(binary_data)
    postamble = generate_postamble()
    
    # Combine signal components
    signal = np.concatenate([vox_preamble, sync_pattern, data_signal, postamble])
    
    # Calculate total duration
    duration = len(signal) / SAMPLE_RATE
    print(f"Signal duration: {duration:.2f} seconds")
    
    # Convert to int16 for audio output
    audio_data = (signal * 32767).astype(np.int16)
    
    # Open audio stream
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=SAMPLE_RATE,
                    output=True)
    
    # Transmit with repeats
    for i in range(repeat):
        if i > 0:
            print(f"Repeat {i+1}/{repeat} - Waiting {delay} seconds...")
            sys.stdout.flush()  # Ensure output is displayed immediately
            time.sleep(delay)
        
        print(f"Transmitting... ({i+1}/{repeat})")
        sys.stdout.flush()
        
        # Transmit audio
        stream.write(audio_data.tobytes())
        print("Transmission complete!")
    
    # Clean up
    stream.stop_stream()
    stream.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VOX-Optimized AFSK Transmitter")
    parser.add_argument("-m", "--message", required=True, help="Message to transmit")
    parser.add_argument("-r", "--repeat", type=int, default=1, help="Number of times to repeat")
    parser.add_argument("-d", "--delay", type=float, default=2, help="Delay between repeats (seconds)")
    parser.add_argument("--vox-pre", type=float, default=VOX_PREAMBLE_DURATION, 
                        help="VOX preamble duration in seconds")
    
    args = parser.parse_args()
    
    # Update VOX preamble duration if specified
    VOX_PREAMBLE_DURATION = args.vox_pre
    
    try:
        transmit(args.message, args.repeat, args.delay)
    finally:
        p.terminate()