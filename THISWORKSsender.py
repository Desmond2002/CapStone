import numpy as np
import sounddevice as sd
import time

MORSE_CODE_DICT = { 
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.',
    'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---',
    'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---',
    'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
    'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--',
    'Z': '--..', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....', '7': '--...',
    '8': '---..', '9': '----.', '0': '-----', ',': '--..--',
    '.': '.-.-.-', '?': '..--..', '/': '-..-.', '-': '-....-',
    '(': '-.--.', ')': '-.--.-', ' ': '/'
}

frequency = 600  # Hz
dot_duration = 0.1  # Seconds

def text_to_morse(text):
    return ' '.join(MORSE_CODE_DICT.get(i.upper(), '') for i in text)
def generate_tone(duration):
    t = np.linspace(0, duration, int(44100 * duration), False)
    return 0.5 * np.sin(2 * np.pi * frequency * t)

def play_morse(morse_code):
    primer = '... / '
    morse_code = primer + morse_code + ' /'
    
    for symbol in morse_code:
        if symbol == '.':
            sd.play(generate_tone(dot_duration), samplerate=44100)
            sd.wait()
            time.sleep(dot_duration)  # Inter-symbol space
        elif symbol == '-':
            sd.play(generate_tone(3*dot_duration), samplerate=44100)
            sd.wait()
            time.sleep(dot_duration)  # Inter-symbol space
        elif symbol == ' ':
            time.sleep(3*dot_duration)  # Inter-character space
        elif symbol == '/':
            time.sleep(7*dot_duration)  # Inter-word space

if __name__ == "__main__":
    message = input("Enter message: ")
    morse = text_to_morse(message)
    print(f"Sending: {morse}")
    play_morse(morse)