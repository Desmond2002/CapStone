#!/usr/bin/env python3
"""
PSK Transmitter - More robust than AFSK for FM radio transmission
"""

import numpy as np
import pyaudio
import argparse
import sys
import time

# PSK Parameters
CARRIER_FREQ = 1500     # Hz - center frequency
SYMBOL_RATE = 200       # Very slow symbol rate for reliability
SAMPLE_RATE = 44100     # Hz
AMPLITUDE = 0.95        # Signal amplitude (0.0-1.0)

# VOX parameters
VOX_ENABLED = True
VOX_PREAMBLE_DURATION = 2.0
VOX_HANGTIME = 0.5

# Reed-Solomon error correction
USE_ERROR_CORRECTION = True
try:
    import reedsolo
    rs = reedsolo.RSCodec(10)  # 10 bytes of error correction
    print("Reed-Solomon error correction enabled")
except ImportError:
    print("Reed-Solomon module not found. Install with: pip install reedsolo")
    USE_ERROR_CORRECTION = False

def add_error_correction(data):
    """Add Reed-Solomon error correction to data"""
    if USE_ERROR_CORRECTION:
        return rs.encode(data)
    return data

def generate_preamble(duration):
    """Generate a preamble tone to trigger VOX and aid synchronization"""
    samples = int(duration * SAMPLE_RATE)
    t = np.arange(samples) / SAMPLE_RATE
    
    # Alternating carrier tone with phase shifts
    signal = np.zeros(samples)
    phase = 0
    blocks = int(duration / 0.1)  # 100ms blocks
    
    for i in range(blocks):
        start = int(i * 0.1 * SAMPLE_RATE)
        end = int((i + 1) * 0.1 * SAMPLE_RATE)
        if end > samples:
            end = samples
            
        if i % 2 == 0:
            signal[start:end] = AMPLITUDE * np.sin(2 * np.pi * CARRIER_FREQ * t[start:end] + phase)
        else:
            signal[start:end] = AMPLITUDE * np.sin(2 * np.pi * CARRIER_FREQ * t[start:end] + phase + np.pi)
            
    return signal

def encode_message(message_bytes):
    """Encode message with PSK modulation"""
    # Start and end markers
    START_MARKER = b'\xAA\xAA\xAA\x7E'
    END_MARKER = b'\x7E\xAA\xAA\xAA'
    
    # Full message with markers and error correction
    full_message = START_MARKER + add_error_correction(message_bytes) + END_MARKER
    
    # Calculate total samples needed
    bits_per_symbol = 1  # Binary PSK
    total_bits = len(full_message) * 8
    symbol_duration = 1.0 / SYMBOL_RATE
    samples_per_symbol = int(symbol_duration * SAMPLE_RATE)
    total_samples = total_bits * samples_per_symbol
    
    # Generate carrier wave
    t = np.arange(total_samples) / SAMPLE_RATE
    carrier = np.sin(2 * np.pi * CARRIER_FREQ * t)
    
    # Modulate carrier with data
    signal = np.zeros(total_samples)
    
    bit_index = 0
    for byte in full_message:
        for bit_pos in range(7, -1, -1):  # MSB first
            bit = (byte >> bit_pos) & 1
            start_sample = bit_index * samples_per_symbol
            end_sample = start_sample + samples_per_symbol
            
            # Use phase 0 for bit 0, phase π (180°) for bit 1
            if bit == 0:
                signal[start_sample:end_sample] = AMPLITUDE * carrier[start_sample:end_sample]
            else:
                signal[start_sample:end_sample] = -AMPLITUDE * carrier[start_sample:end_sample]
                
            bit_index += 1
    
    return signal

def transmit_audio(signal):
    """Transmit audio signal through sound card"""
    audio = pyaudio.PyAudio()
    
    try:
        # Convert to int16
        audio_samples = (signal * 32767).astype(np.int16)
        
        print("Opening audio stream...")
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            output=True
        )
        
        print(f"Playing audio ({len(audio_samples)} samples)...")
        if VOX_ENABLED:
            print("VOX trigger initiated - ensure radio volume is high enough")
        stream.write(audio_samples.tobytes())
        print("Audio playback complete")
        
        stream.stop_stream()
        stream.close()
        
        return True
    except Exception as e:
        print(f"Error transmitting audio: {e}")
        return False
    finally:
        audio.terminate()

def main():
    parser = argparse.ArgumentParser(description="PSK Transmitter")
    parser.add_argument("-m", "--message", type=str, help="Message to transmit")
    parser.add_argument("-f", "--file", type=str, help="File to transmit")
    parser.add_argument("-r", "--repeat", type=int, default=1, help="Number of repetitions")
    parser.add_argument("-d", "--delay", type=float, default=2.0, help="Delay between repetitions")
    
    args = parser.parse_args()
    
    # Get data to transmit
    data = b''
    if args.message:
        print(f"Preparing message: {args.message}")
        data = args.message.encode('utf-8')
    elif args.file:
        try:
            print(f"Reading file: {args.file}")
            with open(args.file, 'rb') as f:
                data = f.read()
        except Exception as e:
            print(f"Error reading file: {e}")
            return 1
    else:
        print("Error: Either message or file must be specified")
        parser.print_help()
        return 1
    
    print(f"Transmitting {len(data)} bytes, {args.repeat} time(s)...")
    print(f"Symbol rate: {SYMBOL_RATE} baud, Carrier: {CARRIER_FREQ} Hz")
    
    if VOX_ENABLED:
        print("IMPORTANT: Radio volume at 80-90%, VOX at level 3+")
    
    for i in range(args.repeat):
        if i > 0:
            print(f"Waiting {args.delay} seconds before next transmission...")
            time.sleep(args.delay)
            
        print(f"Transmission {i+1}/{args.repeat}")
        
        # Generate audio signal
        if VOX_ENABLED:
            preamble = generate_preamble(VOX_PREAMBLE_DURATION)
            postamble = generate_preamble(VOX_HANGTIME)
            message_signal = encode_message(data)
            combined_signal = np.concatenate((preamble, message_signal, postamble))
        else:
            combined_signal = encode_message(data)
        
        # Transmit
        success = transmit_audio(combined_signal)
        
        if success:
            print("Transmission complete!")
        else:
            print("Transmission failed!")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())