#!/usr/bin/env python3
"""
AFSK Receiver - Optimized for Baofeng UV-5R
Updated to handle VOX-enabled transmissions
"""

import numpy as np
import pyaudio
import time
import threading
from collections import deque
import scipy.signal as signal
import argparse
import sys

#=====================================================
# CONFIGURABLE PARAMETERS - Adjust as needed
#=====================================================

# AFSK parameters - must match transmitter settings
MARK_FREQ = 1200      # Hz (binary 1)
SPACE_FREQ = 2200     # Hz (binary 0)
BAUD_RATE = 1200      # bits per second
SAMPLE_RATE = 44100   # Hz

# Receiver parameters
NOISE_FLOOR = 0.008   # Threshold for signal detection (0.0-1.0)
FILTER_BANDWIDTH = 200  # Hz on each side of mark/space frequencies
FILTER_ORDER = 6      # Filter order, higher = sharper but more CPU intensive
BUFFER_SECONDS = 5    # Size of audio buffer in seconds

# Protocol parameters - must match transmitter
START_FLAG_VALUE = 0x7E  # Start flag byte
END_FLAG_VALUE = 0x7E    # End flag byte
ESCAPE_VALUE = 0x7D      # Escape character for byte stuffing
ESCAPE_MASK = 0x20       # XOR mask for escaped bytes

#=====================================================
# End of configurable parameters 
#=====================================================

# Derived protocol constants
START_FLAG = bytes([START_FLAG_VALUE])
END_FLAG = bytes([END_FLAG_VALUE])
ESCAPE = bytes([ESCAPE_VALUE])

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

class Packet:
    def __init__(self, data=None, packet_id=0, packet_type=0):
        self.data = data if data else b''
        self.packet_id = packet_id & 0xFF
        self.packet_type = packet_type & 0xFF
    
    @staticmethod
    def decode(raw_bytes):
        """
        Decode a byte stream into a Packet object
        
        Args:
            raw_bytes (bytes): The received byte stream
            
        Returns:
            Packet: The decoded packet, or None if invalid
        """
        # Find start and end flags
        try:
            # Strip preamble and find start flag
            start_idx = raw_bytes.find(START_FLAG)
            if start_idx == -1:
                return None
                
            # Find end flag after start flag
            end_idx = raw_bytes.find(END_FLAG, start_idx + 1)
            if end_idx == -1:
                return None
                
            # Extract the stuffed frame
            stuffed_frame = raw_bytes[start_idx + 1:end_idx]
            
            # Unstuff the bytes
            unstuffed = bytearray()
            i = 0
            while i < len(stuffed_frame):
                if stuffed_frame[i] == ESCAPE_VALUE:  # Escape character
                    if i + 1 >= len(stuffed_frame):
                        return None  # Invalid escape sequence
                    unstuffed.append(stuffed_frame[i + 1] ^ ESCAPE_MASK)
                    i += 2  # Skip the escape and the escaped byte
                else:
                    unstuffed.append(stuffed_frame[i])
                    i += 1
                    
            # Verify length (at least 4 bytes: 2 for header, 2 for CRC)
            if len(unstuffed) < 4:
                return None
                
            # Extract parts
            frame = bytes(unstuffed)
            payload = frame[:-2]
            received_crc = int.from_bytes(frame[-2:], byteorder='big')
            
            # Verify CRC
            calculated_crc = crc16_xmodem(payload)
            if calculated_crc != received_crc:
                return None  # CRC check failed
                
            # Extract header
            packet_id = payload[0]
            packet_type = payload[1]
            data = payload[2:]
            
            # Create and return the packet
            packet = Packet(data, packet_id, packet_type)
            return packet
            
        except Exception as e:
            print(f"Error decoding packet: {e}")
            return None

def bits_to_bytes(bits):
    """
    Convert a list of bits to bytes
    
    Args:
        bits (list): List of bits (0s and 1s)
        
    Returns:
        bytes: Reconstructed bytes
    """
    # Ensure the number of bits is a multiple of 8
    while len(bits) % 8 != 0:
        bits.append(0)
        
    result = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            if i + j < len(bits):
                byte |= (bits[i + j] << j)
        result.append(byte)
    return bytes(result)

def create_bandpass_filter(low_freq, high_freq, sample_rate=SAMPLE_RATE, order=FILTER_ORDER):
    """
    Create a bandpass filter for the given frequency range
    
    Args:
        low_freq (float): Lower cutoff frequency in Hz
        high_freq (float): Upper cutoff frequency in Hz
        sample_rate (int): Sample rate in Hz
        order (int): Filter order
        
    Returns:
        tuple: (b, a) filter coefficients
    """
    nyquist = 0.5 * sample_rate
    low = low_freq / nyquist
    high = high_freq / nyquist
    b, a = signal.butter(order, [low, high], btype='band')
    return b, a

class AFSKReceiver:
    """AFSK receiver for capturing and decoding data from audio."""
    
    def __init__(self, sample_rate=SAMPLE_RATE, callback=None):
        """
        Initialize the AFSK receiver.
        
        Args:
            sample_rate (int): Audio sample rate in Hz
            callback (callable): Function to call when data is received
        """
        self.sample_rate = sample_rate
        self.bit_duration = 1.0 / BAUD_RATE
        self.audio = pyaudio.PyAudio()
        self.callback = callback
        self.running = False
        self.buffer = deque(maxlen=int(sample_rate * BUFFER_SECONDS))
        self.last_packet_time = 0
        self.recent_packet_data = set()  # Store hashes of recent packets to avoid duplicates
        
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
        print(f"- Noise floor: {NOISE_FLOOR}")
        
    def __del__(self):
        """Clean up resources."""
        self.stop()
        if hasattr(self, 'audio'):
            self.audio.terminate()
        
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """
        Callback for PyAudio stream.
        """
        if status:
            print(f"PyAudio status: {status}")
            
        # Convert bytes to numpy array
        audio_data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Add to buffer
        self.buffer.extend(audio_data)
        
        return (None, pyaudio.paContinue)
    
    def start(self):
        """Start receiving audio."""
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
        """Stop receiving audio."""
        if not self.running:
            return
            
        self.running = False
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
            
        if hasattr(self, 'process_thread'):
            self.process_thread.join(timeout=1.0)
    
    def _process_audio(self):
        """Process received audio to extract data."""
        samples_per_bit = int(self.bit_duration * self.sample_rate)
        noise_floor = NOISE_FLOOR
        last_bits = []
        
        while self.running:
            # Wait for enough data
            if len(self.buffer) < samples_per_bit * 8:
                time.sleep(0.1)
                continue
                
            # Get buffer as numpy array
            buffer_array = np.array(self.buffer)
            
            # Check signal strength
            signal_power = np.mean(np.abs(buffer_array))
            
            # Debug info occasionally
            current_time = time.time()
            if current_time - self.last_packet_time > 5:  # Every 5 seconds without a packet
                if signal_power >= noise_floor * 0.5:  # If there's any significant signal
                    print(f"Signal detected: power={signal_power:.6f}, noise floor={noise_floor}")
                    
            if signal_power < noise_floor:
                # No significant signal detected
                time.sleep(0.1)
                continue
                
            # Process buffer in bit-sized chunks
            bits = []
            energy_ratio_log = []  # For debugging
            
            for i in range(0, len(buffer_array) - samples_per_bit, samples_per_bit):
                chunk = buffer_array[i:i + samples_per_bit]
                
                # Apply filters
                mark_filtered = signal.lfilter(self.mark_filter[0], self.mark_filter[1], chunk)
                space_filtered = signal.lfilter(self.space_filter[0], self.space_filter[1], chunk)
                
                # Calculate energy in each band
                mark_energy = np.sum(mark_filtered**2)
                space_energy = np.sum(space_filtered**2)
                
                # Calculate energy ratio for debugging
                if space_energy > 0:
                    energy_ratio = mark_energy / space_energy
                    energy_ratio_log.append(energy_ratio)
                
                # Determine bit value based on which frequency has more energy
                if mark_energy > space_energy:
                    bits.append(1)
                else:
                    bits.append(0)
            
            # Look for packets only if we have new bits
            if bits != last_bits and len(bits) >= 16:  # At least enough bits for a small packet
                # Try to find a complete packet
                packet_bytes = bits_to_bytes(bits)
                packet = Packet.decode(packet_bytes)
                
                if packet:
                    # Hash the packet data to check for duplicates
                    packet_hash = hash(packet.data)
                    
                    # Only process if not a duplicate (can happen with repeated transmissions)
                    if packet_hash not in self.recent_packet_data:
                        # Add to recent packets
                        self.recent_packet_data.add(packet_hash)
                        if len(self.recent_packet_data) > 10:  # Keep only the most recent packets
                            self.recent_packet_data.pop()
                        
                        # Valid packet found, call the callback
                        if self.callback:
                            self.callback(packet)
                        
                        # Update last packet time
                        self.last_packet_time = time.time()
                        
                        # Print diagnostic info about signal strength
                        if energy_ratio_log:
                            avg_ratio = sum(energy_ratio_log) / len(energy_ratio_log)
                            print(f"Signal quality: power={signal_power:.6f}, mark/space ratio={avg_ratio:.2f}")
                    
                    # Clear most of the buffer but keep the tail in case it contains
                    # the start of another packet
                    retain = min(samples_per_bit * 8, len(self.buffer) // 4)
                    for _ in range(len(self.buffer) - retain):
                        self.buffer.popleft()
            
            last_bits = bits
            time.sleep(0.1)  # Prevent CPU overuse

def receive_callback(packet):
    """
    Callback function for received packets.
    
    Args:
        packet (Packet): The received packet
    """
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

def main():
    """Main entry point for the AFSK receiver."""
    parser = argparse.ArgumentParser(description="AFSK Receiver")
    
    parser.add_argument("-t", "--time", type=int, default=0, 
                       help="Time to listen in seconds (0 for infinite)")
    parser.add_argument("-o", "--output", type=str, 
                       help="File to save received data")
    parser.add_argument("-n", "--noise", type=float, default=NOISE_FLOOR,
                       help=f"Noise floor threshold (default: {NOISE_FLOOR})")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Override noise floor if specified
    global NOISE_FLOOR
    if args.noise != NOISE_FLOOR:
        NOISE_FLOOR = args.noise
        print(f"Noise floor set to: {NOISE_FLOOR}")
    
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
    print("\nStarting AFSK receiver... Press Ctrl+C to stop")
    
    receiver = AFSKReceiver(callback=callback)
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