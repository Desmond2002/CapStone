#!/usr/bin/env python3
"""
PSK Receiver - More robust than AFSK for FM radio reception
"""

import numpy as np
import pyaudio
import time
import threading
from collections import deque
import scipy.signal as signal
import argparse
import sys

# PSK Parameters
CARRIER_FREQ = 1500     # Hz - center frequency
SYMBOL_RATE = 200       # Very slow symbol rate for reliability
SAMPLE_RATE = 44100     # Hz
NOISE_FLOOR = 0.003     # Signal detection threshold

# Buffer size
BUFFER_SECONDS = 10     # Audio buffer size in seconds

# Reed-Solomon error correction
USE_ERROR_CORRECTION = True
try:
    import reedsolo
    rs = reedsolo.RSCodec(10)  # 10 bytes of error correction
    print("Reed-Solomon error correction enabled")
except ImportError:
    print("Reed-Solomon module not found. Install with: pip install reedsolo")
    USE_ERROR_CORRECTION = False

# Debug options
DEBUG_MODE = True

def apply_error_correction(data):
    """Apply Reed-Solomon error correction to data"""
    if USE_ERROR_CORRECTION:
        try:
            return rs.decode(data)[0]  # Return corrected data
        except reedsolo.ReedSolomonError as e:
            print(f"Error correction failed: {e}")
    return data

class PSKReceiver:
    def __init__(self, sample_rate=SAMPLE_RATE, callback=None, noise_floor=NOISE_FLOOR):
        self.sample_rate = sample_rate
        self.symbol_duration = 1.0 / SYMBOL_RATE
        self.audio = pyaudio.PyAudio()
        self.callback = callback
        self.running = False
        self.buffer = deque(maxlen=int(sample_rate * BUFFER_SECONDS))
        self.last_packet_time = 0
        self.noise_floor = noise_floor
        
        # Create bandpass filter for carrier frequency
        nyquist = 0.5 * sample_rate
        low = (CARRIER_FREQ - SYMBOL_RATE) / nyquist
        high = (CARRIER_FREQ + SYMBOL_RATE) / nyquist
        self.bandpass_filter = signal.butter(4, [low, high], btype='band')
        
        print(f"Receiver initialized with:")
        print(f"- Carrier frequency: {CARRIER_FREQ} Hz")
        print(f"- Symbol rate: {SYMBOL_RATE} baud")
        print(f"- Noise floor: {self.noise_floor}")
        
    def __del__(self):
        self.stop()
        if hasattr(self, 'audio'):
            self.audio.terminate()
        
    def _audio_callback(self, in_data, frame_count, time_info, status):
        if status:
            print(f"PyAudio status: {status}")
            
        # Convert bytes to numpy array
        audio_data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Add to buffer
        self.buffer.extend(audio_data)
        
        return (None, pyaudio.paContinue)
    
    def start(self):
        """Start receiving audio"""
        if self.running:
            return
            
        self.running = True
        self.buffer.clear()
        
        # List available input devices
        print("\nAvailable audio input devices:")
        for i in range(self.audio.get_device_count()):
            dev_info = self.audio.get_device_info_by_index(i)
            if dev_info['maxInputChannels'] > 0:
                print(f"  [{i}] {dev_info['name']}")
        print()
        
        # Try to find the default input device
        try:
            default_device_info = self.audio.get_default_input_device_info()
            default_device_index = default_device_info['index']
            print(f"Using default input device: [{default_device_index}] {default_device_info['name']}")
        except:
            default_device_index = None
            print("Could not determine default input device. Using system default.")
        
        # Start audio stream
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=default_device_index,
                frames_per_buffer=1024,
                stream_callback=self._audio_callback
            )
            print("Audio stream opened successfully.")
        except Exception as e:
            print(f"Error opening audio stream: {e}")
            self.running = False
            return
        
        # Start processing thread
        self.process_thread = threading.Thread(target=self._process_audio)
        self.process_thread.daemon = True
        self.process_thread.start()
        print("Audio processing started. Waiting for signals...")
        
    def stop(self):
        """Stop receiving audio"""
        if not self.running:
            return
            
        self.running = False
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
            
        if hasattr(self, 'process_thread'):
            self.process_thread.join(timeout=1.0)
    
    def _process_audio(self):
        """Process received audio to extract data"""
        samples_per_symbol = int(self.symbol_duration * self.sample_rate)
        found_signal = False
        signal_start_time = 0
        
        while self.running:
            # Wait for enough data
            if len(self.buffer) < samples_per_symbol * 32:  # Need at least a few symbols
                time.sleep(0.1)
                continue
            
            # Get buffer as numpy array
            buffer_array = np.array(self.buffer)
            
            # Apply bandpass filter
            filtered = signal.filtfilt(self.bandpass_filter[0], self.bandpass_filter[1], buffer_array)
            
            # Check signal strength
            signal_power = np.mean(np.abs(filtered))
            
            # Debug info
            current_time = time.time()
            if current_time - self.last_packet_time > 5:
                if signal_power >= self.noise_floor:
                    print(f"Signal detected: power={signal_power:.6f}, noise floor={self.noise_floor}")
                    
                    if not found_signal:
                        found_signal = True
                        signal_start_time = current_time
                        print("Signal acquisition started - decoding...")
            
            # Auto-adjust noise floor for long signals without packets
            if found_signal and current_time - signal_start_time > 10 and current_time - self.last_packet_time > 10:
                found_signal = False
                adjusted_noise_floor = signal_power * 0.8
                print(f"Adjusting noise floor from {self.noise_floor} to {adjusted_noise_floor}")
                self.noise_floor = adjusted_noise_floor
                    
            if signal_power < self.noise_floor:
                # No significant signal detected
                time.sleep(0.1)
                continue
            
            # Search for start marker in the signal
            # Using correlation with reference waveform for better detection
            START_MARKER = b'\xAA\xAA\xAA\x7E'
            END_MARKER = b'\x7E\xAA\xAA\xAA'
            
            # Demodulate PSK - use differential phase detection
            symbols = []
            symbol_values = []
            
            for i in range(0, len(filtered) - samples_per_symbol, samples_per_symbol):
                symbol_chunk = filtered[i:i + samples_per_symbol]
                
                # Use a reference carrier at the expected frequency
                t = np.arange(len(symbol_chunk)) / self.sample_rate
                ref_i = np.cos(2 * np.pi * CARRIER_FREQ * t)
                ref_q = np.sin(2 * np.pi * CARRIER_FREQ * t)
                
                # Mix with received signal (complex baseband conversion)
                i_component = np.sum(symbol_chunk * ref_i)
                q_component = np.sum(symbol_chunk * ref_q)
                
                # Extract phase
                phase = np.arctan2(q_component, i_component)
                
                # Differential symbol detection
                if i > 0:
                    # Difference in phase from previous symbol
                    phase_diff = phase - prev_phase
                    
                    # Normalize to -π to π
                    phase_diff = ((phase_diff + np.pi) % (2 * np.pi)) - np.pi
                    
                    # Binary PSK decision
                    if abs(phase_diff) > np.pi/2:  # Phase change > 90°
                        symbol = 1
                    else:
                        symbol = 0
                        
                    symbols.append(symbol)
                    symbol_values.append(phase_diff)
                    
                prev_phase = phase
            
            # Convert symbols to bytes
            if len(symbols) >= 32:  # At least enough for start marker
                # Display bits for debug
                if DEBUG_MODE:
                    bit_str = ''.join(['1' if b else '0' for b in symbols[:100]])
                    print(f"Bits: {bit_str}...")
                
                # Convert bits to bytes
                bytes_data = bytearray()
                byte = 0
                bit_count = 0
                
                for bit in symbols:
                    byte = (byte << 1) | bit
                    bit_count += 1
                    if bit_count == 8:
                        bytes_data.append(byte)
                        byte = 0
                        bit_count = 0
                
                # Search for markers in the byte stream
                start_idx = -1
                end_idx = -1
                
                # Look for START_MARKER
                for i in range(len(bytes_data) - 3):
                    if bytes_data[i:i+4] == START_MARKER:
                        start_idx = i + 4  # Skip marker
                        break
                
                # If start marker found, look for END_MARKER
                if start_idx >= 0:
                    for i in range(start_idx, len(bytes_data) - 3):
                        if bytes_data[i:i+4] == END_MARKER:
                            end_idx = i
                            break
                
                # If both markers found, extract and process the packet
                if start_idx >= 0 and end_idx > start_idx:
                    packet_data = bytes(bytes_data[start_idx:end_idx])
                    
                    # Apply error correction
                    try:
                        if USE_ERROR_CORRECTION:
                            packet_data = apply_error_correction(packet_data)
                    except Exception as e:
                        print(f"Error correction processing error: {e}")
                    
                    # Create packet object for callback
                    class Packet:
                        def __init__(self, data):
                            self.data = data
                            self.packet_id = 0  # Not used in this version
                            self.packet_type = 0  # Not used in this version
                    
                    packet = Packet(packet_data)
                    
                    # Call callback
                    if self.callback:
                        self.callback(packet)
                        
                    # Update last packet time
                    self.last_packet_time = current_time
                    found_signal = False
                    
                    # Clear most of the buffer
                    retain = min(samples_per_symbol * 16, len(self.buffer) // 4)
                    for _ in range(len(self.buffer) - retain):
                        self.buffer.popleft()
            
            time.sleep(0.1)  # Prevent CPU overuse

def receive_callback(packet):
    """Callback for received packets"""
    print("\n===== PACKET RECEIVED =====")
    print(f"Data length: {len(packet.data)} bytes")
    
    # Try to decode as text
    try:
        text = packet.data.decode('utf-8')
        print(f"Text: \"{text}\"")
    except UnicodeDecodeError:
        print(f"Data (hex): {packet.data.hex()}")
        
    # Print timestamp
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("===========================\n")
    
    # Also print on a single line for easier viewing
    try:
        text = packet.data.decode('utf-8')
        short_output = f"DECODED MESSAGE: \"{text}\""
        print("\n" + "=" * len(short_output))
        print(short_output)
        print("=" * len(short_output) + "\n")
    except:
        pass

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="PSK Receiver")
    
    parser.add_argument("-t", "--time", type=int, default=0, 
                       help="Time to listen in seconds (0 for infinite)")
    parser.add_argument("-o", "--output", type=str, 
                       help="File to save received data")
    parser.add_argument("-n", "--noise", type=float, default=NOISE_FLOOR,
                       help=f"Noise floor threshold (default: {NOISE_FLOOR})")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Use the noise floor from arguments if provided
    noise_floor_value = args.noise
    
    # Define a custom callback if output file specified
    callback = receive_callback
    if args.output:
        def file_callback(packet):
            # Call the regular callback first
            receive_callback(packet)
            
            # Also save to file
            try:
                with open(args.output, 'ab') as f:
                    f.write(packet.data)
                print(f"Data appended to {args.output}")
            except Exception as e:
                print(f"Error writing to file: {e}")
                
        callback = file_callback
    
    # Start receiver
    print("\n========================================")
    print("PSK Receiver")
    print("========================================")
    print("Press Ctrl+C to stop")
    
    receiver = PSKReceiver(callback=callback, noise_floor=noise_floor_value)
    receiver.start()
    
    try:
        if args.time > 0:
            # Listen for specified time
            print(f"Will listen for {args.time} seconds")
            time.sleep(args.time)
        else:
            # Listen indefinitely
            print("Listening indefinitely. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping receiver...")
    finally:
        receiver.stop()
        
    return 0

if __name__ == "__main__":
    sys.exit(main())