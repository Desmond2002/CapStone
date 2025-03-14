#!/usr/bin/env python3
"""
Simple AFSK Receiver - No frills, just functionality
"""

import numpy as np
import pyaudio
import time
import argparse
from scipy.signal import butter, lfilter
import threading

# AFSK parameters - must match transmitter
MARK_FREQ = 1200  # Hz (Binary 1)
SPACE_FREQ = 2200 # Hz (Binary 0)
BAUD_RATE = 300   # Baud rate
SAMPLE_RATE = 44100 # Hz

# Detection parameters
NOISE_THRESHOLD = 0.01  # Threshold for signal detection
MIN_SIGNAL_DURATION = 0.5  # Minimum duration (seconds) for valid signal

# Create audio object
p = pyaudio.PyAudio()

def bandpass_filter(data, center_freq, bandwidth=100):
    """Apply a bandpass filter around the target frequency"""
    nyquist = 0.5 * SAMPLE_RATE
    low = (center_freq - bandwidth/2) / nyquist
    high = (center_freq + bandwidth/2) / nyquist
    
    # Create a butterworth filter
    b, a = butter(3, [low, high], btype='band')
    
    # Apply the filter
    return lfilter(b, a, data)

def detect_signal(audio_buffer):
    """Detect if a valid signal is present in the audio buffer"""
    # Look for energy in either MARK or SPACE frequencies
    mark_filtered = bandpass_filter(audio_buffer, MARK_FREQ)
    space_filtered = bandpass_filter(audio_buffer, SPACE_FREQ)
    
    # Calculate signal energy
    mark_energy = np.mean(mark_filtered ** 2)
    space_energy = np.mean(space_filtered ** 2)
    total_energy = mark_energy + space_energy
    
    # Check if above threshold
    return total_energy > NOISE_THRESHOLD

def decode_afsk(audio_buffer):
    """Decode AFSK signal to binary data"""
    # Calculate samples per bit
    samples_per_bit = int(SAMPLE_RATE / BAUD_RATE)
    
    # Filter signal for MARK and SPACE frequencies
    mark_filtered = bandpass_filter(audio_buffer, MARK_FREQ)
    space_filtered = bandpass_filter(audio_buffer, SPACE_FREQ)
    
    # Calculate energy for each bit period
    num_bits = len(audio_buffer) // samples_per_bit
    binary_data = ""
    
    for i in range(num_bits):
        start = i * samples_per_bit
        end = start + samples_per_bit
        
        # Calculate energy in each frequency band
        mark_energy = np.sum(mark_filtered[start:end] ** 2)
        space_energy = np.sum(space_filtered[start:end] ** 2)
        
        # Determine bit value based on which frequency has more energy
        if mark_energy > space_energy:
            binary_data += "1"
        else:
            binary_data += "0"
    
    return binary_data

def binary_to_text(binary_data):
    """Convert binary string to text"""
    # Ensure binary data length is a multiple of 8
    binary_data = binary_data[:len(binary_data) - (len(binary_data) % 8)]
    
    # Convert each 8-bit group to a character
    text = ""
    for i in range(0, len(binary_data), 8):
        byte = binary_data[i:i+8]
        try:
            text += chr(int(byte, 2))
        except ValueError:
            text += "?"
    
    return text

def receive_audio():
    """Main function to receive and process audio"""
    CHUNK = 4410  # 0.1 seconds of audio at 44.1kHz
    
    # Create a buffer for audio data
    audio_buffer = []
    in_signal = False
    signal_start_time = 0
    
    # Set up audio callback function
    def audio_callback(in_data, frame_count, time_info, status):
        # Convert audio data to numpy array
        data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Process data
        process_audio(data)
        
        return (in_data, pyaudio.paContinue)
    
    # Function to process incoming audio
    def process_audio(data):
        nonlocal audio_buffer, in_signal, signal_start_time
        
        # Check if we have a signal
        if not in_signal:
            if detect_signal(data):
                # Signal started
                in_signal = True
                signal_start_time = time.time()
                audio_buffer = []  # Clear buffer
                print("Signal detected - receiving...")
        
        # If we're tracking a signal, add data to buffer
        if in_signal:
            audio_buffer.extend(data)
            
            # Check if signal is still present
            if not detect_signal(data):
                # Signal may have ended
                # Only process if signal was long enough
                signal_duration = time.time() - signal_start_time
                
                if signal_duration >= MIN_SIGNAL_DURATION:
                    print(f"Signal received: {signal_duration:.1f} seconds")
                    
                    # Process in separate thread to not block audio
                    threading.Thread(target=process_signal, 
                                    args=(np.array(audio_buffer),)).start()
                
                # Reset for next signal
                in_signal = False
                audio_buffer = []
    
    # Function to process a complete signal
    def process_signal(signal_data):
        # Decode signal
        binary_data = decode_afsk(signal_data)
        print(f"Binary data length: {len(binary_data)} bits")
        
        # Convert to text
        text = binary_to_text(binary_data)
        print(f"Decoded message: {text}")
        print("-" * 40)
    
    # Open audio input stream
    try:
        # List available input devices
        print("Available input devices:")
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            if dev['maxInputChannels'] > 0:
                print(f"  [{i}] {dev['name']}")
        
        # Try to use default input device
        try:
            default_device = p.get_default_input_device_info()
            device_index = default_device['index']
            print(f"Using default device: [{device_index}] {default_device['name']}")
        except:
            device_index = None
            print("Could not determine default input device. Using system default.")
        
        # Open stream
        stream = p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=SAMPLE_RATE,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=CHUNK,
                        stream_callback=audio_callback)
        
        print("\nListening for AFSK signal...")
        print(f"MARK: {MARK_FREQ} Hz, SPACE: {SPACE_FREQ} Hz, RATE: {BAUD_RATE} baud")
        print("Press Ctrl+C to stop")
        
        # Keep running until interrupted
        stream.start_stream()
        try:
            while stream.is_active():
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            stream.stop_stream()
            stream.close()
            
    finally:
        p.terminate()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple AFSK Receiver")
    parser.add_argument("-t", "--threshold", type=float, default=NOISE_THRESHOLD,
                        help=f"Signal detection threshold (default: {NOISE_THRESHOLD})")
    
    args = parser.parse_args()
    
    # Update threshold if provided
    NOISE_THRESHOLD = args.threshold
    
    receive_audio()