import numpy as np
import pyaudio
import time
import re
from scipy import signal
import threading
import queue

# AFSK parameters (must match sender)
SAMPLE_RATE = 44100  # Hz
MARK_FREQ = 1200     # Hz (binary 1)
SPACE_FREQ = 2200    # Hz (binary 0)
BAUD_RATE = 1200     # bits per second
SAMPLES_PER_BIT = int(SAMPLE_RATE / BAUD_RATE)
CHUNK_SIZE = 1024    # Audio buffer size

# Create bandpass filters for mark and space frequencies
def create_bandpass_filter(center_freq, bandwidth):
    """Create a bandpass filter for the given center frequency"""
    nyquist = SAMPLE_RATE / 2.0
    low = (center_freq - bandwidth/2) / nyquist
    high = (center_freq + bandwidth/2) / nyquist
    b, a = signal.butter(3, [low, high], btype='band')
    return b, a

# Create our filters
MARK_FILTER = create_bandpass_filter(MARK_FREQ, 300)
SPACE_FILTER = create_bandpass_filter(SPACE_FREQ, 300)

class AFSKReceiver:
    def __init__(self):
        self.bit_buffer = []
        self.char_buffer = ""
        self.packet_buffer = ""
        self.receiving = False
        self.last_bit = None
        self.bit_count = 0
        self.last_transition = 0
        self.debug_mode = False
        
    def set_debug(self, debug):
        """Enable or disable debug mode"""
        self.debug_mode = debug
        
    def process_bit(self, bit):
        """Process a decoded bit, looking for start/stop bits pattern"""
        # Look for bit transitions to help with synchronization
        if self.last_bit is not None and self.last_bit != bit:
            if self.debug_mode:
                print(f"Bit transition: {self.last_bit} -> {bit}")
            self.last_transition = 0
        else:
            self.last_transition += 1
        
        # If we've seen too many of the same bit in a row, we might be out of sync
        if self.last_transition > 20:  # Arbitrary threshold
            if self.receiving and self.debug_mode:
                print("Too many identical bits - resetting receiver")
            self.receiving = False
            self.bit_count = 0
            self.bit_buffer = []
            self.last_transition = 0
        
        if not self.receiving:
            # Looking for start bit (0)
            if bit == 0 and (self.last_bit == 1 or self.last_bit is None):
                self.receiving = True
                self.bit_buffer = [0]  # Start bit
                self.bit_count = 1
                if self.debug_mode:
                    print("Start bit detected - beginning character reception")
        else:
            # Add bit to buffer
            self.bit_buffer.append(bit)
            self.bit_count += 1
            
            # Check if we have a complete character (10 bits)
            if self.bit_count == 10:
                self.decode_character()
                self.receiving = False
                self.bit_count = 0
                
        self.last_bit = bit
    
    def decode_character(self):
        """Decode 10 bits (start bit + 8 data bits + stop bit) to ASCII character"""
        # Check if start and stop bits are valid
        if self.bit_buffer[0] != 0 or self.bit_buffer[9] != 1:
            # Invalid framing
            if self.debug_mode:
                print(f"Invalid framing bits: start={self.bit_buffer[0]}, stop={self.bit_buffer[9]}")
            self.bit_buffer = []
            return
            
        # Extract the 8 data bits and convert to decimal
        ascii_val = 0
        for i in range(8):
            if self.bit_buffer[i+1] == 1:
                ascii_val |= (1 << i)
        
        # Convert to character and add to buffer
        char = chr(ascii_val)
        self.char_buffer += char
        
        if self.debug_mode:
            print(f"Decoded character: '{char}' ({ascii_val})")
        
        # Check for packet pattern
        if char == '*' or "TEMP:" in self.char_buffer or "TEST:" in self.char_buffer:
            self.packet_buffer += self.char_buffer
            self.char_buffer = ""
            self.check_packet()
    
    def check_packet(self):
        """Check if we have a complete packet and extract data"""
        # Check for temperature pattern
        temp_match = re.search(r'TEMP:([\d.]+)\*([0-9A-F]{2})', self.packet_buffer)
        if temp_match:
            temp_str = temp_match.group(1)
            checksum_str = temp_match.group(2)
            
            # Verify checksum
            calculated_checksum = sum(ord(c) for c in f"TEMP:{temp_str}") % 256
            received_checksum = int(checksum_str, 16)
            
            if calculated_checksum == received_checksum:
                try:
                    temp = float(temp_str)
                    print(f"\nRECEIVED TEMPERATURE: {temp}Â°C [Checksum OK]")
                except ValueError:
                    print(f"\nError converting temperature value: {temp_str}")
            else:
                print(f"\nChecksum error! Received: {checksum_str}, Calculated: {calculated_checksum:02X}")
            
            # Reset packet buffer but keep anything after the matched pattern
            self.packet_buffer = self.packet_buffer[temp_match.end():]
            return
            
        # Check for test message pattern
        test_match = re.search(r'TEST:([A-Z]+)\*([0-9A-F]{2})', self.packet_buffer)
        if test_match:
            message = test_match.group(1)
            checksum_str = test_match.group(2)
            
            # Verify checksum
            calculated_checksum = sum(ord(c) for c in f"TEST:{message}") % 256
            received_checksum = int(checksum_str, 16)
            
            if calculated_checksum == received_checksum:
                print(f"\nRECEIVED TEST MESSAGE: '{message}' [Checksum OK]")
            else:
                print(f"\nTest message checksum error! Received: {checksum_str}, Calculated: {calculated_checksum:02X}")
                
            # Reset packet buffer but keep anything after the matched pattern
            self.packet_buffer = self.packet_buffer[test_match.end():]
            return
        
        # If buffer gets too long without matching, trim it
        elif len(self.packet_buffer) > 100:
            if self.debug_mode:
                print("Trimming packet buffer (too long without match)")
            self.packet_buffer = self.packet_buffer[-50:]  # Keep last 50 chars

def audio_callback(in_data, frame_count, time_info, status, audio_queue):
    """Callback for PyAudio"""
    if status:
        print(f"Status: {status}")
    
    # Convert byte data to numpy array
    audio_data = np.frombuffer(in_data, dtype=np.float32)
    
    # Add to queue
    audio_queue.put(audio_data)
    
    return (in_data, pyaudio.paContinue)

def process_audio_data(audio_data, receiver):
    """Process a chunk of audio data for AFSK decoding"""
    # Get maximum level for display
    level = np.max(np.abs(audio_data))
    
    # Process the chunk in bit-sized segments
    for i in range(0, len(audio_data), SAMPLES_PER_BIT):
        if i + SAMPLES_PER_BIT > len(audio_data):
            break  # Not enough samples for a full bit
            
        # Get a chunk of samples that represents one bit
        bit_chunk = audio_data[i:i+SAMPLES_PER_BIT]
        
        # Apply bandpass filters
        mark_signal = signal.lfilter(MARK_FILTER[0], MARK_FILTER[1], bit_chunk)
        space_signal = signal.lfilter(SPACE_FILTER[0], SPACE_FILTER[1], bit_chunk)
        
        # Calculate energy in the filtered signals
        mark_energy = np.sum(np.abs(mark_signal) ** 2)
        space_energy = np.sum(np.abs(space_signal) ** 2)
        
        # Determine bit based on which frequency has more energy
        bit = 1 if mark_energy > space_energy else 0
        
        # Process the bit
        receiver.process_bit(bit)
    
    return level

def processing_thread(audio_queue, receiver, level_queue):
    """Thread to process audio data from queue"""
    while True:
        try:
            chunk = audio_queue.get(timeout=1.0)
            if chunk is None:  # Special value to signal thread to exit
                break
            
            level = process_audio_data(chunk, receiver)
            level_queue.put(level)
            
            audio_queue.task_done()
        except queue.Empty:
            # Just continue if no data
            continue
        except Exception as e:
            print(f"Error in processing thread: {str(e)}")

def main():
    print("AFSK Cable Receiver")
    print("=================")
    print("This script receives AFSK signals via 2.5mm to 3.5mm cable")
    
    print("\nSETUP INSTRUCTIONS:")
    print("1. Connect 2.5mm end of the cable to your radio's speaker output")
    print("2. Connect 3.5mm end of the cable to your computer's microphone/line-in input")
    print("3. Set your radio to the correct frequency and turn up the volume to ~70%")
    
    # Ask if user wants debug mode
    debug_mode = input("\nEnable debug output? (y/n): ").lower().startswith('y')
    
    # Initialize the receiver
    receiver = AFSKReceiver()
    receiver.set_debug(debug_mode)
    audio_queue = queue.Queue(maxsize=10)
    level_queue = queue.Queue(maxsize=10)
    
    # Create and start processing thread
    proc_thread = threading.Thread(target=processing_thread, args=(audio_queue, receiver, level_queue))
    proc_thread.daemon = True
    proc_thread.start()
    
    # Initialize PyAudio
    p = pyaudio.PyAudio()
    
    # List available audio input devices
    print("\nAvailable audio inputs:")
    for i in range(p.get_device_count()):
        dev_info = p.get_device_info_by_index(i)
        if dev_info['maxInputChannels'] > 0:  # Only input devices
            print(f"  [{i}] {dev_info['name']}")
    
    # Ask user to select input device
    try:
        device_index = int(input("\nSelect audio input number for your cable: ").strip())
    except ValueError:
        print("Invalid selection. Using default audio input.")
        device_index = None
    
    try:
        # Open audio stream
        stream = p.open(format=pyaudio.paFloat32,
                        channels=1,
                        rate=SAMPLE_RATE,
                        input=True,
                        frames_per_buffer=CHUNK_SIZE,
                        input_device_index=device_index if device_index is not None else None,
                        stream_callback=lambda in_data, frame_count, time_info, status: 
                                       audio_callback(in_data, frame_count, time_info, status, audio_queue))
        
        print("\nAudio input opened. Listening for AFSK signals...")
        print("Press Ctrl+C to stop.")
        
        # Show audio level
        print("\nAudio level (should show activity when receiving):")
        
        while True:
            time.sleep(0.1)
            
            # Get level if available
            try:
                level = level_queue.get(block=False)
                level_queue.task_done()
                
                # Create level bar
                bars = int(level * 50)  # Scale to 0-50 bars
                bars = min(bars, 50)    # Cap at 50
                level_bar = "â–ˆ" * bars + "â–‘" * (50 - bars)
                
                print(f"\rLevel: {level:.4f} [{level_bar}]", end="", flush=True)
            except queue.Empty:
                # No new level data, just continue
                pass
            
    except KeyboardInterrupt:
        print("\n\nReceiver stopped by user.")
    except Exception as e:
        print(f"\n\nError: {str(e)}")
    finally:
        # Clean up
        if 'stream' in locals() and stream.is_active():
            stream.stop_stream()
            stream.close()
        
        # Signal processing thread to exit
        audio_queue.put(None)
        proc_thread.join(timeout=1.0)
        
        p.terminate()
        print("\nAudio resources released.")

if __name__ == "__main__":
    main()