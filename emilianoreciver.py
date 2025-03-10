#!/usr/bin/env python3
"""
Baofeng UV-5R Data Receiver
Decodes audio from the radio into data via 3.5mm audio input.
"""

import numpy as np
import pyaudio
import time
import struct
from scipy import signal
import matplotlib.pyplot as plt

class BaofengDataReceiver:
    def __init__(self, mark_freq=1200, space_freq=2200, baud_rate=300, sample_rate=44100):
        """
        Initialize the receiver with audio parameters.
        
        Args:
            mark_freq: Frequency representing binary 1 (Hz)
            space_freq: Frequency representing binary 0 (Hz)
            baud_rate: Transmission speed (bits per second)
            sample_rate: Audio sample rate (samples per second)
        """
        self.mark_freq = mark_freq
        self.space_freq = space_freq
        self.baud_rate = baud_rate
        self.sample_rate = sample_rate
        self.samples_per_bit = int(sample_rate / baud_rate)
        self.p = pyaudio.PyAudio()
        
    def __del__(self):
        """Clean up PyAudio resources when done."""
        self.p.terminate()
    
    def list_audio_devices(self):
        """List available audio input devices."""
        print("Available audio input devices:")
        for i in range(self.p.get_device_count()):
            dev_info = self.p.get_device_info_by_index(i)
            if dev_info['maxInputChannels'] > 0:
                print(f"Device {i}: {dev_info['name']}")
        
        print("\nEnter the number for the device connected to your Baofeng radio:")
        try:
            device_index = int(input("> "))
            return device_index
        except ValueError:
            print("Using default input device.")
            return None
    
    def start_receiving(self, duration=30, input_device_index=None):
        """
        Start receiving audio for the specified duration.
        
        Args:
            duration: How long to record audio (in seconds)
            input_device_index: Optional specific input device to use
        """
        # Create a stream to record audio
        stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.sample_rate,
            input=True,
            input_device_index=input_device_index,
            frames_per_buffer=self.samples_per_bit
        )
        
        print(f"Listening for {duration} seconds...")
        frames = []
        
        # Record audio for the specified duration
        for _ in range(0, int(self.sample_rate / self.samples_per_bit * duration)):
            data = stream.read(self.samples_per_bit, exception_on_overflow=False)
            frames.append(data)
        
        # Close the stream
        stream.stop_stream()
        stream.close()
        
        # Convert the recorded audio to numpy array
        audio_data = np.frombuffer(b''.join(frames), dtype=np.float32)
        
        # Process the received audio
        self.process_audio(audio_data)
    
    def process_audio(self, audio_data):
        """
        Process the received audio to extract the data.
        
        This is a simplified implementation that would need more robust 
        signal processing for real-world use.
        """
        # Create band-pass filters for mark and space frequencies
        mark_filter = self.create_bandpass_filter(self.mark_freq)
        space_filter = self.create_bandpass_filter(self.space_freq)
        
        # Apply the filters to the audio data
        mark_signal = signal.lfilter(mark_filter, 1.0, audio_data)
        space_signal = signal.lfilter(space_filter, 1.0, audio_data)
        
        # Compute the energy in each band
        mark_energy = np.array([np.sum(mark_signal[i:i+self.samples_per_bit]**2) 
                              for i in range(0, len(mark_signal), self.samples_per_bit)])
        space_energy = np.array([np.sum(space_signal[i:i+self.samples_per_bit]**2) 
                               for i in range(0, len(space_signal), self.samples_per_bit)])
        
        # Determine bits based on which frequency has more energy
        bits = (mark_energy > space_energy).astype(int)
        
        # Look for preamble pattern to find the start of data
        self.decode_bits(bits)
        
        # Optional: Visualize the signal
        self.visualize_signal(mark_energy, space_energy, bits)
        
    def visualize_signal(self, mark_energy, space_energy, bits):
        """Visualize the received signal for debugging."""
        plt.figure(figsize=(12, 6))
        
        # Plot energies
        plt.subplot(2, 1, 1)
        plt.plot(mark_energy, label='Mark (1200 Hz)')
        plt.plot(space_energy, label='Space (2200 Hz)')
        plt.legend()
        plt.title('Signal Energy')
        
        # Plot bits
        plt.subplot(2, 1, 2)
        plt.step(range(len(bits)), bits)
        plt.ylim(-0.1, 1.1)
        plt.title('Decoded Bits')
        
        plt.tight_layout()
        plt.show()
        
    def create_bandpass_filter(self, center_freq, bandwidth=100):
        """Create a simple bandpass filter."""
        nyquist = 0.5 * self.sample_rate
        low = (center_freq - bandwidth/2) / nyquist
        high = (center_freq + bandwidth/2) / nyquist
        b = signal.firwin(101, [low, high], pass_zero=False)
        return b
    
    def decode_bits(self, bits):
        """
        Decode the bit stream into characters.
        This is a simplified implementation and would need more robust 
        pattern matching and error correction for real-world use.
        """
        # Look for preamble (alternating 1s and 0s)
        preamble_pattern = [1, 0] * 5
        
        # Find potential starts of messages
        for i in range(len(bits) - len(preamble_pattern)):
            if np.array_equal(bits[i:i+len(preamble_pattern)], preamble_pattern):
                # Found potential preamble, try to decode message
                self.decode_message(bits[i+len(preamble_pattern):])
    
    def decode_message(self, bits):
        """
        Attempt to decode a message from the bit stream.
        """
        # Simple UART-style decoding (start bit, 8 data bits, stop bit)
        i = 0
        message = ""
        
        while i < len(bits) - 10:  # Need at least 10 bits for a character
            # Check for start bit (should be 0)
            if bits[i] == 0:
                # Extract 8 data bits
                byte_bits = bits[i+1:i+9]
                byte_val = sum(bit << idx for idx, bit in enumerate(byte_bits))
                
                # Check stop bit (should be 1)
                if bits[i+9] == 1:
                    message += chr(byte_val)
                    i += 10  # Move to next character
                else:
                    i += 1  # Not a valid character, move forward
            else:
                i += 1  # Not a start bit, move forward
        
        if message:
            print(f"Decoded message: {message}")
            if "TEMP:" in message:
                parts = message.split(",")
                temp = parts[0].split(":")[1] if len(parts) > 0 and ":" in parts[0] else "unknown"
                time = parts[1].split(":")[1] if len(parts) > 1 and ":" in parts[1] else "unknown"
                print(f"Temperature: {temp}, Time: {time}")
        
def main():
    receiver = BaofengDataReceiver()
    
    # List available audio devices and let user select one
    input_device_index = receiver.list_audio_devices()
    
    try:
        while True:
            # Listen for transmissions
            receiver.start_receiving(duration=15, input_device_index=input_device_index)
            
            # Option to quit
            response = input("Press Enter to listen again or 'q' to quit: ")
            if response.lower() == 'q':
                break
                
    except KeyboardInterrupt:
        print("\nReceiver stopped by user")

if __name__ == "__main__":
    main()