
import numpy as np
import time
import re
from scipy import signal
import pyaudio
import threading
import queue

# AFSK parameters (must match sender)
SAMPLE_RATE = 44100  # Hz
MARK_FREQ = 1200     # Hz (binary 1)
SPACE_FREQ = 2200    # Hz (binary 0)
BAUD_RATE = 1200     # bits per second
SAMPLES_PER_BIT = int(SAMPLE_RATE / BAUD_RATE)

# Buffer size for audio input
CHUNK_SIZE = 1024
AUDIO_BUFFER_SIZE = 10  # Number of chunks to buffer

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
        if char == '*' or "TEMP:" in self.char_buffer:
            self.packet_buffer += self.char_buffer
            self.char_buffer = ""
            self.check_packet()
    
    def check_packet(self):
        """Check if we have a complete packet and extract temperature data"""
        # Look for the pattern TEMP:<value>*<checksum>
        match = re.search(r'TEMP:([\d.]+)\*([0-9A-F]{2})', self.packet_buffer)
        if match:
            temp_str = match.group(1)
            checksum_str = match.group(2)
            
            # Verify checksum
            calculated_checksum = sum(ord(c) for c in f"TEMP:{temp_str}") % 256
            received_checksum = int(checksum_str, 16)
            
            if calculated_checksum == received_checksum:
                try:
                    temp = float(temp_str)
                    print(f"\nReceived temperature: {temp}°C [Checksum OK]")
                except ValueError:
                    print(f"\nError converting temperature value: {temp_str}")
            else:
                print(f"\nChecksum error! Received: {checksum_str}, Calculated: {calculated_checksum:02X}")
            
            # Reset packet buffer but keep anything after the matched pattern
            self.packet_buffer = self.packet_buffer[match.end():]
        
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

def processing_thread(audio_queue, receiver):
    """Thread to process audio data from queue"""
    while True:
        try:
            chunk = audio_queue.get(timeout=1.0)
            if chunk is None:  # Special value to signal thread to exit
                break
            
            # Process the chunk in bit-sized segments
            for i in range(0, len(chunk), SAMPLES_PER_BIT):
                if i + SAMPLES_PER_BIT > len(chunk):
                    break  # Not enough samples for a full bit
                    
                # Get a chunk of samples that represents one bit
                bit_chunk = chunk[i:i+SAMPLES_PER_BIT]
                
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
                
            audio_queue.task_done()
        except queue.Empty:
            # Just continue if no data
            continue
        except Exception as e:
            print(f"Error in processing thread: {str(e)}")

def main():
    print("AFSK Temperature Receiver")
    print("========================")
    print("This script receives and decodes AFSK temperature data")
    
    print("\nIMPORTANT SETUP INSTRUCTIONS:")
    print("1. Connect the USB programming cable to your computer")
    print("2. Connect the other end to your Baofeng radio's speaker port")
    print("3. Ensure the radio is on and tuned to the same frequency as the transmitter")
    print("4. Set the volume to around 70-80% on the receiver radio")
    
    print("\nParameters:")
    print(f"- Mark frequency: {MARK_FREQ} Hz (binary 1)")
    print(f"- Space frequency: {SPACE_FREQ} Hz (binary 0)")
    print(f"- Baud rate: {BAUD_RATE} bps")
    print(f"- Sample rate: {SAMPLE_RATE} Hz")
    
    # Ask if user wants debug mode
    debug_mode = input("\nEnable debug output? (y/n): ").lower().startswith('y')
    
    receiver = AFSKReceiver()
    receiver.set_debug(debug_mode)
    audio_queue = queue.Queue(maxsize=AUDIO_BUFFER_SIZE)
    
    # Create and start processing thread
    proc_thread = threading.Thread(target=processing_thread, args=(audio_queue, receiver))
    proc_thread.daemon = True
    proc_thread.start()
    
    # Initialize PyAudio
    p = pyaudio.PyAudio()
    
    # List available audio input devices
    print("\nAvailable audio input devices:")
    for i in range(p.get_device_count()):
        dev_info = p.get_device_info_by_index(i)
        if dev_info['maxInputChannels'] > 0:  # Only input devices
            print(f"  [{i}] {dev_info['name']}")
    
    # Ask user to select input device
    try:
        device_index = int(input("\nSelect input device number (typically the USB Programming Cable): ").strip())
    except ValueError:
        print("Invalid selection. Using default input device.")
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
        
        print("\nAudio stream started. Listening for AFSK signals...")
        print("Press Ctrl+C to stop.")
        
        # Keep the main thread running
        while True:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nReceiver stopped by user.")
    except Exception as e:
        print(f"\nError: {str(e)}")
    finally:
        # Clean up
        if 'stream' in locals() and stream.is_active():
            stream.stop_stream()
            stream.close()
        
        # Signal processing thread to exit
        audio_queue.put(None)
        proc_thread.join(timeout=1.0)
        
        p.terminate()
        print("Audio resources released.")

if __name__ == "__main__":
    main()