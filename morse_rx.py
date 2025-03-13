#!/usr/bin/env python3
"""
Simple Morse Code Receiver - Better pattern recognition
"""

import numpy as np
import pyaudio
import time
import threading
from collections import deque
import scipy.signal as signal
import argparse
import sys

# Morse code parameters
TONE_FREQ = 800       # Hz - must match transmitter
WPM_DEFAULT = 5       # Words per minute (must match transmitter)
SAMPLE_RATE = 44100   # Hz
NOISE_FLOOR = 0.005   # Higher threshold for cleaner detection

# Buffer size
BUFFER_SECONDS = 15   # Larger audio buffer for complete messages

# Debug options
DEBUG_MODE = True

# Morse code definitions
MORSE_CODE_REVERSE = {
    '.-': 'A',     '-...': 'B',   '-.-.': 'C',
    '-..': 'D',    '.': 'E',      '..-.': 'F',
    '--.': 'G',    '....': 'H',   '..': 'I',
    '.---': 'J',   '-.-': 'K',    '.-..': 'L',
    '--': 'M',     '-.': 'N',     '---': 'O',
    '.--.': 'P',   '--.-': 'Q',   '.-.': 'R',
    '...': 'S',    '-': 'T',      '..-': 'U',
    '...-': 'V',   '.--': 'W',    '-..-': 'X',
    '-.--': 'Y',   '--..': 'Z',
    '-----': '0',  '.----': '1',  '..---': '2',
    '...--': '3',  '....-': '4',  '.....': '5',
    '-....': '6',  '--...': '7',  '---..': '8',
    '----.': '9',
    '.-.-.-': '.',  '--..--': ',',  '/': ' '
}

# Special patterns
SOS_PATTERN = '... --- ...'  # Start marker
AR_PATTERN = '.-.-.'         # End marker

class SimpleMorseReceiver:
    def __init__(self, sample_rate=SAMPLE_RATE, callback=None, noise_floor=NOISE_FLOOR, wpm=WPM_DEFAULT):
        self.sample_rate = sample_rate
        self.audio = pyaudio.PyAudio()
        self.callback = callback
        self.running = False
        self.buffer = deque(maxlen=int(sample_rate * BUFFER_SECONDS))
        self.last_decode_time = 0
        self.noise_floor = noise_floor
        self.wpm = wpm
        
        # Calculate timings based on WPM
        self.dot_duration = 1.5 / self.wpm  # seconds (matches transmitter)
        self.dash_duration = 3 * self.dot_duration
        self.element_gap = self.dot_duration * 1.2
        self.letter_gap = 3 * self.dot_duration * 1.2
        self.word_gap = 7 * self.dot_duration * 1.2
        
        # Create bandpass filter for tone frequency
        nyquist = 0.5 * sample_rate
        low = (TONE_FREQ - 100) / nyquist  # Wider filter bandwidth
        high = (TONE_FREQ + 100) / nyquist
        self.bandpass_filter = signal.butter(2, [low, high], btype='band')
        
        print(f"Receiver initialized with:")
        print(f"- Tone frequency: {TONE_FREQ} Hz")
        print(f"- Speed: {self.wpm} WPM")
        print(f"- Dot duration: {self.dot_duration:.3f}s")
        print(f"- Dash duration: {self.dash_duration:.3f}s")
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
        print("Audio processing started. Waiting for Morse signals...")
        
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
            
    def _extract_morse_from_envelope(self, envelope):
        """Extract Morse code elements from the signal envelope"""
        dot_samples = int(self.dot_duration * self.sample_rate * 0.8)  # More permissive
        dash_samples = int(self.dash_duration * self.sample_rate * 0.8)
        letter_gap_samples = int(self.letter_gap * self.sample_rate * 0.8)
        word_gap_samples = int(self.word_gap * self.sample_rate * 0.8)
        
        morse_pattern = []
        in_tone = False
        tone_start = 0
        last_tone_end = 0
        gap_start = 0
        
        # Apply adaptive threshold
        threshold = max(self.noise_floor, np.mean(envelope) * 0.3)
        
        # Process the envelope
        i = 0
        while i < len(envelope):
            # Rising edge detection
            if not in_tone and envelope[i] > threshold:
                in_tone = True
                tone_start = i
                gap_duration = i - last_tone_end if last_tone_end > 0 else 0
                
                # Check if we should add a letter or word gap
                if gap_duration >= word_gap_samples:
                    morse_pattern.append('/')
                    if DEBUG_MODE:
                        print("/", end='', flush=True)
                elif gap_duration >= letter_gap_samples:
                    morse_pattern.append(' ')
                    if DEBUG_MODE:
                        print(" ", end='', flush=True)
            
            # Falling edge detection
            elif in_tone and envelope[i] <= threshold:
                in_tone = False
                tone_duration = i - tone_start
                last_tone_end = i
                
                # Classify as dot or dash
                if tone_duration >= dot_samples:
                    if tone_duration < dash_samples:
                        morse_pattern.append('.')
                        if DEBUG_MODE:
                            print(".", end='', flush=True)
                    else:
                        morse_pattern.append('-')
                        if DEBUG_MODE:
                            print("-", end='', flush=True)
            
            i += 1
            
        if DEBUG_MODE and len(morse_pattern) > 0:
            print()  # New line after dots and dashes
            
        return ''.join(morse_pattern)
    
    def _process_audio(self):
        """Process received audio to decode Morse code"""
        found_signal = False
        signal_start_time = 0
        complete_pattern = []
        
        while self.running:
            # Wait for enough data
            min_samples = int(self.dot_duration * self.sample_rate)
            if len(self.buffer) < min_samples * 10:
                time.sleep(0.1)
                continue
            
            # Get buffer as numpy array
            buffer_array = np.array(self.buffer)
            
            # Apply bandpass filter to isolate tone frequency
            filtered = signal.filtfilt(self.bandpass_filter[0], self.bandpass_filter[1], buffer_array)
            
            # Calculate envelope for tone detection
            analytic_signal = signal.hilbert(filtered)
            envelope = np.abs(analytic_signal)
            
            # Smooth envelope for cleaner transitions
            window_size = int(0.02 * self.sample_rate)  # 20ms window
            if window_size > 1:
                smoothed_envelope = np.convolve(envelope, np.ones(window_size)/window_size, mode='same')
            else:
                smoothed_envelope = envelope
            
            # Get current signal level
            signal_level = np.mean(smoothed_envelope[-1024:])
            
            # Debug info
            current_time = time.time()
            if current_time - self.last_decode_time > 5:
                if signal_level >= self.noise_floor:
                    print(f"Signal detected: level={signal_level:.6f}, noise floor={self.noise_floor}")
                    
                    if not found_signal:
                        found_signal = True
                        signal_start_time = current_time
                        print("Morse signal acquisition started - decoding...")
                        complete_pattern = []  # Reset pattern buffer on new signal
            
            # Auto-adjust noise floor for long signals without decodes
            if found_signal and current_time - signal_start_time > 20 and current_time - self.last_decode_time > 20:
                found_signal = False
                adjusted_noise_floor = signal_level * 0.7
                print(f"Adjusting noise floor from {self.noise_floor} to {adjusted_noise_floor}")
                self.noise_floor = adjusted_noise_floor
            
            # Process this chunk of audio if signal is present
            if signal_level >= self.noise_floor:
                # Extract Morse pattern from this chunk
                chunk_pattern = self._extract_morse_from_envelope(smoothed_envelope)
                
                if chunk_pattern:
                    # Add to complete pattern
                    complete_pattern.append(chunk_pattern)
                
                    # Check for complete message (look for start and end markers)
                    complete_morse = ''.join(complete_pattern)
                    
                    # Try to decode what we have so far - even without markers
                    if len(complete_morse) > 10:  # Reasonable minimum length
                        # Look for message boundaries or just work with what we have
                        self._attempt_decode(complete_morse)
            
            time.sleep(0.1)  # Prevent CPU overuse
            
    def _attempt_decode(self, morse_string):
        """Try to decode a complete or partial morse string"""
        # First check if we have a complete message with markers
        sos_pos = morse_string.find(SOS_PATTERN)
        ar_pos = morse_string.find(AR_PATTERN)
        
        if sos_pos >= 0 and ar_pos > sos_pos:
            # We have markers - extract the message part
            message_morse = morse_string[sos_pos + len(SOS_PATTERN):ar_pos]
            self._decode_and_report(message_morse, True)
        else:
            # No markers or incomplete - try to decode what we have
            self._decode_and_report(morse_string, False)
                
    def _decode_and_report(self, morse_pattern, is_complete):
        """Decode and report a message"""
        # Clean up the pattern
        morse_pattern = morse_pattern.replace('//', '/').replace('  ', ' ').strip()
        
        if DEBUG_MODE:
            print(f"\nDecoding{'(COMPLETE)' if is_complete else ''}: {morse_pattern}")
        
        # Decode the pattern
        decoded_text = ""
        for code in morse_pattern.split(' '):
            if code in MORSE_CODE_REVERSE:
                decoded_text += MORSE_CODE_REVERSE[code]
            elif code == '/':
                decoded_text += ' '
            elif code and len(code) > 0:
                # Unknown pattern
                decoded_text += '?'
        
        # Create packet object for callback
        class Packet:
            def __init__(self, data, pattern, is_complete):
                self.data = data
                self.morse_pattern = pattern
                self.is_complete = is_complete
        
        if len(decoded_text) > 0:
            packet = Packet(decoded_text.encode('utf-8'), morse_pattern, is_complete)
            
            # Call callback
            if self.callback:
                self.callback(packet)
                
            # Update last decode time
            self.last_decode_time = time.time()

def receive_callback(packet):
    """Callback for received packets"""
    prefix = "COMPLETE" if packet.is_complete else "PARTIAL"
    
    print(f"\n===== MORSE DECODED ({prefix}) =====")
    print(f"Pattern: {packet.morse_pattern}")
    
    # Try to decode as text
    try:
        text = packet.data.decode('utf-8')
        print(f"Text: \"{text}\"")
    except UnicodeDecodeError:
        print(f"Data (hex): {packet.data.hex()}")
        
    # Print timestamp
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("========================\n")
    
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
    parser = argparse.ArgumentParser(description="Simple Morse Code Receiver")
    
    parser.add_argument("-t", "--time", type=int, default=0, 
                       help="Time to listen in seconds (0 for infinite)")
    parser.add_argument("-o", "--output", type=str, 
                       help="File to save received text")
    parser.add_argument("-n", "--noise", type=float, default=NOISE_FLOOR,
                       help=f"Noise floor threshold (default: {NOISE_FLOOR})")
    parser.add_argument("-w", "--wpm", type=int, default=WPM_DEFAULT,
                       help=f"Words per minute (default: {WPM_DEFAULT})")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Use the noise floor from arguments if provided
    noise_floor_value = args.noise
    wpm_value = args.wpm
    
    # Define a custom callback if output file specified
    callback = receive_callback
    if args.output:
        def file_callback(packet):
            # Call the regular callback first
            receive_callback(packet)
            
            # Also save to file
            try:
                with open(args.output, 'a') as f:
                    text = packet.data.decode('utf-8', errors='replace')
                    f.write(text + "\n")
                print(f"Text appended to {args.output}")
            except Exception as e:
                print(f"Error writing to file: {e}")
                
        callback = file_callback
    
    # Start receiver
    print("\n========================================")
    print("Simple Morse Code Receiver")
    print("========================================")
    print("Press Ctrl+C to stop")
    
    receiver = SimpleMorseReceiver(callback=callback, noise_floor=noise_floor_value, wpm=wpm_value)
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
