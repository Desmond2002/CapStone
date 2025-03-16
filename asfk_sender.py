import numpy as np
import pyaudio
import time
import sys
import threading
from scipy import signal

# AFSK Parameters optimized for Baofeng UV-5RX
SAMPLE_RATE = 44100       # Standard audio sample rate
MARK_FREQ = 1000          # Mark frequency (binary '1') - lower for Baofeng bandwidth
SPACE_FREQ = 1600         # Space frequency (binary '0') - lower for Baofeng bandwidth
BAUD_RATE = 100           # Slower baud rate for better reliability on handheld radios
BIT_LENGTH = int(SAMPLE_RATE / BAUD_RATE)  # Samples per bit

# Protocol parameters - extended for Baofeng reliability
PREAMBLE_BITS = 128       # Longer preamble for VOX triggering
START_MARKER = '10101010' * 8  # Longer start marker
END_MARKER = '01010101' * 8    # Longer end marker

def text_to_binary(text):
    """Convert text to binary string"""
    binary = ''
    for char in text:
        binary += format(ord(char), '08b')
    return binary

def binary_to_text(binary):
    """Convert binary string to text"""
    text = ''
    # Process in chunks of 8 bits (1 byte)
    for i in range(0, len(binary), 8):
        byte = binary[i:i+8]
        if len(byte) == 8:  # Ensure we have a complete byte
            text += chr(int(byte, 2))
    return text

def generate_preamble():
    """Generate alternating bit sequence for VOX triggering and sync"""
    preamble = ''
    for i in range(PREAMBLE_BITS):
        preamble += '1' if i % 2 == 0 else '0'
    return preamble

def add_protocol_framing(binary_data):
    """Add protocol framing (preamble and markers) to binary data"""
    preamble = generate_preamble()
    return preamble + START_MARKER + binary_data + END_MARKER

def calculate_phase_continuity(prev_phase, frequency, samples):
    """Calculate phase to ensure continuity between tone transitions"""
    angular_freq = 2 * np.pi * frequency / SAMPLE_RATE
    return prev_phase + angular_freq * samples

class AFSKTransmitter:
    def __init__(self, debug=False):
        self.sample_rate = SAMPLE_RATE
        self.mark_freq = MARK_FREQ
        self.space_freq = SPACE_FREQ
        self.baud_rate = BAUD_RATE
        self.bit_length = BIT_LENGTH
        self.debug = debug
        
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.phase = 0  # For phase continuity
    
    def generate_afsk_signal(self, binary_data):
        """Generate AFSK signal from binary data with phase continuity"""
        # Add protocol framing (preamble + markers)
        framed_data = add_protocol_framing(binary_data)
        
        # Create audio buffer
        audio_buffer = np.zeros(len(framed_data) * self.bit_length, dtype=np.float32)
        
        if self.debug:
            print(f"Generating AFSK signal for {len(framed_data)} bits ({len(framed_data)/8:.1f} bytes)")
            print(f"Total audio length: {len(framed_data) * self.bit_length / self.sample_rate:.2f}s")
        
        # Generate tones for each bit with phase continuity
        for i, bit in enumerate(framed_data):
            start_idx = i * self.bit_length
            end_idx = start_idx + self.bit_length
            
            # Select frequency based on bit value
            freq = self.mark_freq if bit == '1' else self.space_freq
            
            # Generate time array for this bit
            t = np.arange(self.bit_length)
            
            # Calculate the signal with phase continuity
            self.phase = calculate_phase_continuity(self.phase, freq, self.bit_length)
            
            # Generate the tone with proper phase
            audio_buffer[start_idx:end_idx] = np.sin(
                2 * np.pi * freq * t / self.sample_rate + self.phase)
            
            # Debug output every 8 bits
            if self.debug and i % 16 == 0 and i > 0:
                part = "PREAMBLE" if i < PREAMBLE_BITS else (
                      "START" if i < PREAMBLE_BITS + len(START_MARKER) else (
                      "END" if i >= PREAMBLE_BITS + len(START_MARKER) + len(binary_data) else "DATA"))
                print(f"Bit {i}: {bit} → {freq}Hz [{part}]")
        
        # Apply smoother fade in/out for Baofeng's AGC
        fade_len = int(self.bit_length * 0.25)  # 25% of a bit length for smoother transition
        fade_in = np.linspace(0, 1, fade_len)
        fade_out = np.linspace(1, 0, fade_len)
        
        audio_buffer[:fade_len] *= fade_in
        audio_buffer[-fade_len:] *= fade_out
        
        # Lower output level for Baofeng input sensitivity
        audio_buffer = 0.5 * audio_buffer / np.max(np.abs(audio_buffer))
        
        return audio_buffer
    
    def transmit_message(self, text_message):
        """Convert text to AFSK and transmit"""
        # Convert text to binary
        binary_data = text_to_binary(text_message)
        
        print("\n====== BAOFENG AFSK TRANSMITTER ======")
        print(f"Message: {text_message}")
        print(f"Binary: {binary_data[:32]}..." + ("" if len(binary_data) <= 32 else f" ({len(binary_data)} bits)"))
        
        # Generate AFSK signal
        afsk_signal = self.generate_afsk_signal(binary_data)
        
        # Setup audio output stream
        self.stream = self.audio.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.sample_rate,
            output=True
        )
        
        # Calculate transmission time
        tx_time = len(afsk_signal) / self.sample_rate
        
        print("\n[TRANSMITTING]")
        print(f"↪ Duration: {tx_time:.2f} seconds")
        print(f"↪ Baud Rate: {self.baud_rate} bps")
        print(f"↪ MARK: {self.mark_freq}Hz / SPACE: {self.space_freq}Hz")
        
        # Create progress indicators
        total_chunks = 20
        chunk_size = len(afsk_signal) // total_chunks
        
        # Add longer lead time for Baofeng PTT activation (1.2 seconds)
        print("↪ PTT lead-in: 1.2 seconds")
        silence_lead = np.zeros(int(self.sample_rate * 2.0), dtype=np.float32)
        self.stream.write(silence_lead.tobytes())
        
        # Transmit the AFSK signal with progress indication
        print("\nProgress: ", end="", flush=True)
        for i in range(total_chunks):
            if i < total_chunks - 1:
                chunk = afsk_signal[i*chunk_size:(i+1)*chunk_size]
            else:
                # Last chunk might be larger due to integer division
                chunk = afsk_signal[i*chunk_size:]
                
            self.stream.write(chunk.tobytes())
            print("▓", end="", flush=True)
        print(" Complete!")
        
        # Add trailing silence for clean release
        silence_trail = np.zeros(int(self.sample_rate * 0.8), dtype=np.float32)
        self.stream.write(silence_trail.tobytes())
        
        print("\n[TRANSMISSION COMPLETE]")
        print("============================\n")
        
        # Clean up
        self.stream.stop_stream()
        self.stream.close()
    
    def close(self):
        """Clean up resources"""
        if self.stream:
            self.stream.close()
        self.audio.terminate()

def main():
    # Parse command line arguments
    debug_mode = False
    message = None
    
    for arg in sys.argv[1:]:
        if arg == "--debug":
            debug_mode = True
        elif not message:  # First non-flag argument is the message
            message = arg
        else:  # Append additional arguments to message
            message += " " + arg
    
    transmitter = AFSKTransmitter(debug=debug_mode)
    
    try:
        if not message:
            message = input("Enter message to transmit: ")
        
        transmitter.transmit_message(message)
    
    except KeyboardInterrupt:
        print("\n\nTransmission interrupted.")
    finally:
        transmitter.close()

if __name__ == "__main__":
    main()