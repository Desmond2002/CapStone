import numpy as np
import pyaudio
import time
import random

# AFSK parameters
SAMPLE_RATE = 44100  # Hz - standard audio sample rate
MARK_FREQ = 1200     # Hz - frequency representing binary 1
SPACE_FREQ = 2200    # Hz - frequency representing binary 0
BAUD_RATE = 1200     # Bits per second - standard for amateur radio AFSK
SAMPLES_PER_BIT = int(SAMPLE_RATE / BAUD_RATE)
PACKET_PAUSE = 3     # Seconds between packet transmissions
VOLUME = 0.7         # Audio volume (0.0 to 1.0)

# Initialize PyAudio once
p = pyaudio.PyAudio()

def generate_tone(freq, duration):
    """Generate a sine wave tone at the specified frequency and duration"""
    samples = (np.sin(2 * np.pi * np.arange(SAMPLE_RATE * duration) * freq / SAMPLE_RATE)).astype(np.float32)
    return VOLUME * samples

def play_sound(audio_data):
    """Play audio data directly"""
    stream = p.open(format=pyaudio.paFloat32, channels=1, rate=SAMPLE_RATE, output=True)
    stream.write(audio_data.tobytes())
    stream.stop_stream()
    stream.close()

def char_to_bits(char):
    """Convert a character to bits with start and stop bits (UART-like format)"""
    ascii_val = ord(char)
    # Start bit (0) + 8 data bits + Stop bit (1)
    bits = [0]  # Start bit
    # LSB first (standard for serial)
    for i in range(8):
        bits.append((ascii_val >> i) & 1)
    bits.append(1)  # Stop bit
    return bits

def string_to_bits(data_str):
    """Convert an entire string to a sequence of bits"""
    bits = []
    for char in data_str:
        bits.extend(char_to_bits(char))
    return bits

def generate_afsk(bits):
    """Generate AFSK audio signal from a sequence of bits"""
    audio = np.array([], dtype=np.float32)
    
    # Add a strong preamble tone to help trigger VOX
    preamble_tone = generate_tone(MARK_FREQ, 0.5)
    audio = np.append(audio, preamble_tone)
    
    # Add alternating bits preamble to help receiver synchronize
    preamble_bits = [0, 1] * 16  # 32 bits of alternating 0s and 1s
    for bit in preamble_bits:
        if bit == 1:
            audio = np.append(audio, generate_tone(MARK_FREQ, 1/BAUD_RATE))
        else:
            audio = np.append(audio, generate_tone(SPACE_FREQ, 1/BAUD_RATE))
    
    # Generate audio for data bits
    for bit in bits:
        if bit == 1:
            audio = np.append(audio, generate_tone(MARK_FREQ, 1/BAUD_RATE))
        else:
            audio = np.append(audio, generate_tone(SPACE_FREQ, 1/BAUD_RATE))
    
    # Add a postamble
    postamble_bits = [1, 0] * 8
    for bit in postamble_bits:
        if bit == 1:
            audio = np.append(audio, generate_tone(MARK_FREQ, 1/BAUD_RATE))
        else:
            audio = np.append(audio, generate_tone(SPACE_FREQ, 1/BAUD_RATE))
            
    return audio

def get_temperature():
    """Simulate a temperature sensor reading between 20°C and 30°C"""
    return round(random.uniform(20.0, 30.0), 1)

def create_packet(temp):
    """Format temperature data into a packet with start/end markers"""
    packet = f"TEMP:{temp}"
    
    # Add a simple checksum (sum of ASCII values modulo 256)
    checksum = sum(ord(c) for c in packet) % 256
    packet += f"*{checksum:02X}"
    
    return packet

def create_test_message():
    """Create a simple test message"""
    message = "TEST"
    packet = f"TEST:{message}"
    
    # Add a simple checksum
    checksum = sum(ord(c) for c in packet) % 256
    packet += f"*{checksum:02X}"
    
    return packet

def main():
    print("AFSK Cable Transmitter")
    print("=====================")
    print("This script generates AFSK signals and sends them via audio cable")
    
    print("\nMODES:")
    print("1. Temperature data")
    print("2. Test message")
    
    mode = input("\nSelect mode (1-2): ").strip()
    test_mode = (mode == "2")
    
    print("\nSETUP INSTRUCTIONS:")
    print("1. Connect 3.5mm cable from computer's headphone out to radio's microphone port")
    print("2. Enable VOX mode on your Baofeng radio (MENU + 4) or prepare to press PTT manually")
    print("3. Adjust VOX sensitivity if needed")
    
    # Ask about PTT method
    ptt_method = input("\nAre you using VOX mode or manual PTT? (VOX/manual): ").strip().lower()
    manual_ptt = ptt_method.startswith('m')
    
    try:
        print("\nParameters:")
        print(f"- Mark frequency: {MARK_FREQ} Hz (binary 1)")
        print(f"- Space frequency: {SPACE_FREQ} Hz (binary 0)")
        print(f"- Baud rate: {BAUD_RATE} bps")
        print(f"- Sample rate: {SAMPLE_RATE} Hz")
        print(f"- Mode: {'Test message' if test_mode else 'Temperature data'}")
        
        print("\nPress Ctrl+C to stop.")
        
        count = 1
        while True:
            # Create packet based on selected mode
            if test_mode:
                packet = create_test_message()
                print(f"\n[{count}] Sending test message")
            else:
                temp = get_temperature()
                packet = create_packet(temp)
                print(f"\n[{count}] Temperature: {temp}°C")
                
            print(f"Packet: {packet}")
            
            # Convert to bits
            bits = string_to_bits(packet)
            print(f"Encoding {len(bits)} bits")
            
            # Generate AFSK audio
            audio = generate_afsk(bits)
            
            # Transmit the audio
            if manual_ptt:
                input("\nPress ENTER, then quickly press and hold PTT on your radio...")
                time.sleep(1)  # Give user time to press PTT
                
            print("Transmitting AFSK signal...")
            play_sound(audio)
            
            # Wait between transmissions
            print(f"Waiting {PACKET_PAUSE} seconds before next transmission")
            time.sleep(PACKET_PAUSE)
            count += 1
            
    except KeyboardInterrupt:
        print("\nTransmission stopped by user.")
    except Exception as e:
        print(f"\nError: {str(e)}")
    finally:
        # Clean up PyAudio
        p.terminate()

if __name__ == "__main__":
    main()
