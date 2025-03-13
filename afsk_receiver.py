#!/usr/bin/env python3
"""
Robust AFSK Receiver - Production version with enhanced reliability
"""

import numpy as np
import pyaudio
import time
import threading
from collections import deque
import scipy.signal as signal
import argparse
import sys

# AFSK parameters - must match transmitter
MARK_FREQ = 1200      # Hz (binary 1)
SPACE_FREQ = 2200     # Hz (binary 0)
BAUD_RATE = 300       # Reduced baud rate for better reliability
SAMPLE_RATE = 44100   # Hz

# Receiver parameters
NOISE_FLOOR = 0.003   # Threshold for signal detection
FILTER_BANDWIDTH = 300  # Hz on each side of mark/space
FILTER_ORDER = 4      # Filter order
BUFFER_SECONDS = 5    # Audio buffer size in seconds

# Protocol constants - must match transmitter
SYNC_PATTERN = [0xAA, 0xAA, 0xAA, 0xAA]  # First 4 bytes of sync
START_BYTE = 0x7E                       # Start/end byte

# Debug options
DEBUG_MODE = True

# CRC-16 XMODEM implementation
def crc16_xmodem(data):
    crc = 0x0000
    poly = 0x1021
    
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

def bits_to_bytes_msb_first(bits):
    """Convert bits to bytes (MSB first)"""
    result = bytearray()
    for i in range(0, len(bits), 8):
        if i + 8 <= len(bits):
            byte = 0
            for j in range(8):
                byte |= (bits[i + j] << (7 - j))
            result.append(byte)
    return bytes(result)

def create_bandpass_filter(low_freq, high_freq, sample_rate=SAMPLE_RATE, order=FILTER_ORDER):
    """Create a bandpass filter"""
    nyquist = 0.5 * sample_rate
    low = low_freq / nyquist
    high = high_freq / nyquist
    b, a = signal.butter(order, [low, high], btype='band')
    return b, a

class AFSKReceiver:
    """AFSK receiver for capturing and decoding data from audio"""
    
    def __init__(self, sample_rate=SAMPLE_RATE, callback=None, noise_floor=NOISE_FLOOR):
        self.sample_rate = sample_rate
        self.bit_duration = 1.0 / BAUD_RATE
        self.audio = pyaudio.PyAudio()
        self.callback = callback
        self.running = False
        self.buffer = deque(maxlen=int(sample_rate * BUFFER_SECONDS))
        self.last_packet_time = 0
        self.noise_floor = noise_floor
        
        # Create filters for mark and space frequencies
        self.mark_filter = create_bandpass_filter(
            MARK_FREQ - FILTER_BANDWIDTH, 
            MARK_FREQ + FILTER_BANDWIDTH, 
            sample_rate
        )
        self.space_filter = create_bandpass_filter(
            SPACE_FREQ - FILTER_BANDWIDTH, 
            SPACE_FREQ + FILTER_BANDWIDTH, 
            sample_rate
        )
        
        print(f"Receiver initialized with:")
        print(f"- Mark frequency: {MARK_FREQ} Hz")
        print(f"- Space frequency: {SPACE_FREQ} Hz")
        print(f"- Baud rate: {BAUD_RATE} bps")
        print(f"- Filter bandwidth: {FILTER_BANDWIDTH} Hz")
        print(f"- Noise floor: {self.noise_floor}")
        
    def __del__(self):
        """Clean up resources"""
        self.stop()
        if hasattr(self, 'audio'):
            self.audio.terminate()
        
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback"""
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
            if dev_info['maxInputChannels'] > 0:  # Only show input devices
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
        samples_per_bit = int(self.bit_duration * self.sample_rate)
        last_bits = []
        found_signal = False
        signal_start_time = 0
        
        while self.running:
            # Wait for enough data
            if len(self.buffer) < samples_per_bit * 16:  # Need at least a few bytes
                time.sleep(0.1)
                continue
                
            # Get buffer as numpy array
            buffer_array = np.array(self.buffer)
            
            # Check signal strength
            signal_power = np.mean(np.abs(buffer_array))
            
            # Debug info
            current_time = time.time()
            if current_time - self.last_packet_time > 5:  # Every 5 seconds without a packet
                if signal_power >= self.noise_floor:  # If there's any significant signal
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
                
            # Process buffer in bit-sized chunks
            bits = []
            
            # Increased sampling density for better bit recovery
            step_size = max(1, samples_per_bit // 8)  # Take 8 samples per bit period
            
            for i in range(0, len(buffer_array) - samples_per_bit, step_size):
                chunk = buffer_array[i:i + samples_per_bit]
                
                # Apply filters
                mark_filtered = signal.lfilter(self.mark_filter[0], self.mark_filter[1], chunk)
                space_filtered = signal.lfilter(self.space_filter[0], self.space_filter[1], chunk)
                
                # Calculate energy in each band
                mark_energy = np.sum(mark_filtered**2)
                space_energy = np.sum(space_filtered**2)
                
                # Determine bit value
                if mark_energy > space_energy:
                    bits.append(1)
                else:
                    bits.append(0)
            
            # Consolidate repeated bits from oversampling
            consolidated_bits = []
            if len(bits) > 0:
                current_bit = bits[0]
                count = 1
                
                for bit in bits[1:]:
                    if bit == current_bit:
                        count += 1
                    else:
                        # Add the bit, taking the majority over ~8 samples
                        for _ in range(max(1, count // 8)):
                            consolidated_bits.append(current_bit)
                        current_bit = bit
                        count = 1
                
                # Add the final bit
                for _ in range(max(1, count // 8)):
                    consolidated_bits.append(current_bit)
            
            bits = consolidated_bits
            
            # Debug bit display
            if DEBUG_MODE and len(bits) > 20:
                bit_str = ''.join(['1' if b else '0' for b in bits[:100]])
                print(f"Bits: {bit_str}...")
            
            # Convert bits to bytes for packet searching
            if len(bits) >= 32:  # At least enough for sync pattern + start byte
                bytes_data = bits_to_bytes_msb_first(bits)
                
                # Look for sync pattern and start byte
                for i in range(len(bytes_data) - 9):  # Need at least 9 bytes for a minimal packet
                    # Check for sync pattern (at least part of it)
                    if (bytes_data[i:i+2] == b'\xAA\xAA' and 
                        bytes_data[i+8] == START_BYTE):
                        
                        if DEBUG_MODE:
                            print(f"Found potential packet at position {i}")
                            
                        # We found a potential packet start, try to parse it
                        packet_start = i + 9  # After sync and start byte
                        
                        # Extract packet ID and type
                        if packet_start + 2 <= len(bytes_data):
                            packet_id = bytes_data[packet_start]
                            packet_type = bytes_data[packet_start + 1]
                            
                            # Extract length (16-bit value)
                            if packet_start + 4 <= len(bytes_data):
                                data_len = int.from_bytes(bytes_data[packet_start+2:packet_start+4], byteorder='big')
                                
                                # Sanity check on length
                                if 0 <= data_len <= 1000:  # Reasonable maximum size
                                    # Check if we have enough bytes for the complete packet
                                    expected_end = packet_start + 4 + data_len + 2  # Header + data + CRC
                                    
                                    if expected_end + 1 <= len(bytes_data) and bytes_data[expected_end] == START_BYTE:
                                        # We have a complete packet!
                                        
                                        # Extract data and CRC
                                        data = bytes_data[packet_start+4:packet_start+4+data_len]
                                        received_crc = int.from_bytes(bytes_data[expected_end-2:expected_end], byteorder='big')
                                        
                                        # Calculate CRC
                                        header = bytes([packet_id, packet_type])
                                        len_bytes = data_len.to_bytes(2, byteorder='big')
                                        crc_data = header + len_bytes + data
                                        calculated_crc = crc16_xmodem(crc_data)
                                        
                                        if DEBUG_MODE:
                                            print(f"Packet: ID={packet_id}, Type={packet_type}, Len={data_len}")
                                            print(f"CRC: calculated={calculated_crc:04x}, received={received_crc:04x}")
                                        
                                        if calculated_crc == received_crc:
                                            print("VALID CRC - Packet received successfully!")
                                            
                                            # Create packet object for callback
                                            class Packet:
                                                def __init__(self, data, packet_id, packet_type):
                                                    self.data = data
                                                    self.packet_id = packet_id
                                                    self.packet_type = packet_type
                                            
                                            packet = Packet(data, packet_id, packet_type)
                                            
                                            # Call callback
                                            if self.callback:
                                                self.callback(packet)
                                                
                                            # Update last packet time
                                            self.last_packet_time = current_time
                                            found_signal = False
                                            
                                            # Clear most of the buffer
                                            retain = min(samples_per_bit * 16, len(self.buffer) // 4)
                                            for _ in range(len(self.buffer) - retain):
                                                self.buffer.popleft()
                                                
                                            # Break out of the loop to avoid processing the same packet again
                                            break
            
            last_bits = bits
            time.sleep(0.1)  # Prevent CPU overuse

def receive_callback(packet):
    """Callback for received packets"""
    print("\n===== PACKET RECEIVED =====")
    print(f"Packet ID: {packet.packet_id}")
    print(f"Packet Type: {packet.packet_type}")
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
    parser = argparse.ArgumentParser(description="Robust AFSK Receiver")
    
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
    print("Robust AFSK Receiver")
    print("========================================")
    print("Press Ctrl+C to stop")
    
    receiver = AFSKReceiver(callback=callback, noise_floor=noise_floor_value)
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