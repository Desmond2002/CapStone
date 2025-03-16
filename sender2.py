import numpy as np
import sounddevice as sd
import time

# Morse Code Dictionary
MORSE_CODE_DICT = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.',
    'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---',
    'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---',
    'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
    'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--',
    'Z': '--..', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....', '7': '--...',
    '8': '---..', '9': '----.', '0': '-----', ', ': '--..--',
    '.': '.-.-.-', '?': '..--..', '/': '-..-.', '-': '-....-',
    '(': '-.--.', ')': '-.--.-', ' ': '/'
}

# Settings
frequency = 600  # Hz tone frequency (typical Morse frequency)
dot_duration = 0.1  # Seconds per dot


def text_to_morse(text):
    return ' '.join(MORSE_CODE_DICT.get(i.upper(), '') for i in text)


def generate_tone(duration):
    samplerate = 44100
    t = np.linspace(0, duration, int(samplerate * duration), False)
    tone = np.sin(frequency * t * 2 * np.pi)
    return tone


def play_morse(morse_code):
    # Start with three dots followed by a word space
    primer = '... / '
    morse_code = primer + morse_code

    for symbol in morse_code:
        if symbol == '.':
            tone = generate_tone(dot_duration)
            sd.play(tone, samplerate=44100)
            sd.wait()
            time.sleep(dot_duration)
        elif symbol == '-':
            tone = generate_tone(dot_duration * 3)
            sd.play(tone, samplerate=44100)
            sd.wait()
            time.sleep(dot_duration)
        elif symbol == ' ':
            time.sleep(dot_duration * 3)
        elif symbol == '/':
            time.sleep(dot_duration * 7)
        time.sleep(dot_duration)


if __name__ == "__main__":
    message = input("Enter the message to send in Morse: ")
    morse_code = text_to_morse(message)
    primer = '... / '
    morse_code = primer + morse_code
    print(f"Sending Morse: {morse_code}")
    play_morse(morse_code)