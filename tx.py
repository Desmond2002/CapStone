import numpy as np
import sounddevice as sd
import time
from datetime import datetime

# Optimized Morse code for digits 0-9 and # (no spaces)
MORSE_CODE = {
    '0': '-',
    '1': '.',
    '2': '.-',
    '3': '..-',
    '4': '...-',
    '5': '....-',
    '6': '-....',
    '7': '-.-',
    '8': '--.',
    '9': '---',
    '#': '-...-'
}

frequency = 600  # Hz
dot_duration = 0.2  # Seconds
dash_duration = 0.5  # Seconds
inter_symbol_pause = dot_duration  # Between dots/dashes
inter_char_pause = 3 * dot_duration  # Between characters
word_pause = 1.0  # Between words (not used)

def generate_tone(duration):
    t = np.linspace(0, duration, int(44100 * duration), False)
    return 0.5 * np.sin(2 * np.pi * frequency * t)

def play_morse(code):
    for symbol in code:
        if symbol == '.':
            sd.play(generate_tone(dot_duration), samplerate=44100)
            sd.wait()
            time.sleep(inter_symbol_pause)
        elif symbol == '-':
            sd.play(generate_tone(dash_duration), samplerate=44100)
            sd.wait()
            time.sleep(inter_symbol_pause)
        elif symbol == ' ':  # Only for #
            time.sleep(inter_char_pause)

def encode_message(data):
    return ''.join([MORSE_CODE[c] for c in data])

if __name__ == "__main__":
    # Generate data (pad with leading zeros)
    device_id = "01"
    packet = f"{datetime.now().hour * 60 + datetime.now().minute:04d}"
    sensor1 = "333"
    sensor2 = "444"
    sensor3 = "555"
    
    data_str = device_id + packet + sensor1 + sensor2 + sensor3
    
    # Calculate checksum (XOR of all digits)
    checksum = 0
    for c in data_str:
        checksum ^= int(c)
    checksum_str = f"{checksum % 10}"
    
    full_msg = f"#{data_str}{checksum_str}#"
    print("Encoded message:", full_msg)
    
    # Convert to Morse code
    morse = []
    for c in full_msg:
        morse.append(MORSE_CODE.get(c, ''))
        morse.append(' ')  # Add space between characters
    
    morse_str = ' '.join(morse)  # Add inter-character pauses
    print("Morse sequence:", morse_str)
    
    # Transmit
    for c in full_msg:
        code = MORSE_CODE.get(c, '')
        for symbol in code:
            play_morse(symbol)
        time.sleep(inter_char_pause)  # Pause after each character
    time.sleep(word_pause)  # Final pause
