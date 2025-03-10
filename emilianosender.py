### Sender Script (Transmitter)

import numpy as np
import sounddevice as sd
import time
import random
import wave
import pyaudio
import serial

# AFSK parameters
SAMPLE_RATE = 44100  # Hz - standard audio sample rate
MARK_FREQ = 1200     # Hz - frequency representing binary 1
SPACE_FREQ = 2200    # Hz - frequency representing binary 0
BAUD_RATE = 1200     # Bits per second - standard for amateur radio AFSK
SAMPLES_PER_BIT = int(SAMPLE_RATE / BAUD_RATE)
PACKET_PAUSE = 3     # Seconds between packet transmissions

def generate_tone(freq, duration):
    """Generate a sine wave tone at the specified frequency and duration"""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    # Lower amplitude of 0.3 to avoid overdriving the radio
    tone = 0.3 * np.sin(2 * np.pi * freq * t)
    return tone

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
    audio = np.array([])
    
    # Add a longer preamble of alternating bits to help receiver synchronize and trigger VOX
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
    
    # Add a short postamble
    postamble_bits = [0, 1] * 4
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

def play_audio(audio, device_id=None):
    """Play audio through the computer's audio output"""
    # Add a short silence at the beginning to ensure VOX triggering works properly
    silence_start = np.zeros(int(SAMPLE_RATE * 0.5))  # 0.5 second of silence
    
    # Add a short silence at the end too
    silence_end = np.zeros(int(SAMPLE_RATE * 0.5))  # 0.5 second of silence
    
    # Combine the audio
    full_audio = np.concatenate((silence_start, audio, silence_end))
    
    # Initialize PyAudio
    p = pyaudio.PyAudio()
    
    # List available audio output devices
    """"""
    if device_id is None:
        print("\nAvailable audio output devices:")
        for i in range(p.get_device_count()):
            dev_info = p.get_device_info_by_index(i)
            if dev_info['maxOutputChannels'] > 0:  # Only output devices
                print(f"  [{i}] {dev_info['name']}")
        
        # Ask user to select output device
        try:
            device_id = int(input("\nSelect output device number for radio connection: ").strip())
        except ValueError:
            print("Invalid selection. Using default output device.")
            device_id = None
    
    try:
        # Open stream
        stream = p.open(format=pyaudio.paFloat32,
                       channels=1,
                       rate=SAMPLE_RATE,
                       output=True,
                       output_device_index=device_id)
        
        # Play audio
        print("Playing audio...")
        stream.write(full_audio.astype(np.float32).tobytes())
        
        # Clean up
        stream.stop_stream()
        stream.close()
    finally:
        p.terminate()
    
    # Save to a WAV file (useful for debugging or manual playback)
    with wave.open("temperature_afsk.wav", "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 2 bytes = 16 bits
        wav_file.setframerate(SAMPLE_RATE)
        # Convert float to int16 for WAV file
        wav_file.writeframes((full_audio * 32767).astype(np.int16).tobytes())

def main():
    print("AFSK Temperature Transmitter")
    print("============================")
    print("This script generates simulated temperature readings")
    print("and transmits them using AFSK modulation.")
    
    print("\nIMPORTANT SETUP INSTRUCTIONS:")
    print("1. Connect 3.5mm to 3.5mm cable from computer's headphone out to radio's microphone port")
    print("2. Enable VOX mode on your Baofeng radio (MENU + 4) or prepare to press PTT manually")
    print("3. Adjust VOX sensitivity if using VOX mode")
    
    # Ask about PTT method
    ptt_method = input("\nAre you using VOX mode or manual PTT? (VOX/manual): ").strip().lower()
    manual_ptt = ptt_method.startswith('m')
    
    # Store the selected output device ID
    selected_device_id = None
    
    try:
        print("\nParameters:")
        print(f"- Mark frequency: {MARK_FREQ} Hz (binary 1)")
        print(f"- Space frequency: {SPACE_FREQ} Hz (binary 0)")
        print(f"- Baud rate: {BAUD_RATE} bps")
        print(f"- Sample rate: {SAMPLE_RATE} Hz")
        print(f"- PTT method: {'Manual' if manual_ptt else 'VOX'}")
        
        print("\nPress Ctrl+C to stop.")
        
        count = 1
        while True:
            # Get temperature reading
            temp = get_temperature()
            print(f"\n[{count}] Temperature: {temp}°C")
            
            # Create packet with temperature data
            packet = create_packet(temp)
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
            play_audio(audio, selected_device_id)
            
            # Store the selected device ID for subsequent transmissions
            if selected_device_id is None:
                selected_device_id = sd.default.device[1]  # Get the current default output device
            
            # Wait between transmissions
            print(f"Waiting {PACKET_PAUSE} seconds before next transmission")
            time.sleep(PACKET_PAUSE)
            count += 1
            
    except KeyboardInterrupt:
        print("\nTransmission stopped by user.")

if __name__ == "__main__":
    main()