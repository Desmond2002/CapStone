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
frequency = 600        # Hz
dot_duration = 0.1     # Duration of a dot in seconds
samplerate = 44100     # Audio sample rate

def text_to_morse(text):
    return ' '.join(MORSE_CODE_DICT.get(i.upper(), '') for i in text)

def generate_tone(duration):
    t = np.linspace(0, duration, int(samplerate * duration), False)
    tone = np.sin(frequency * t * 2 * np.pi)
    return tone

def generate_silence(duration):
    return np.zeros(int(samplerate * duration))

def play_audio(audio):
    sd.play(audio, samplerate=samplerate)
    sd.wait()

def play_morse(morse_code):
    # Initial silence (critical fix)
    play_audio(generate_silence(0.5))
    time.sleep(0.1)  # Slight pause after silence

    for symbol in morse_code:
        if symbol == '.':
            tone = generate_tone(dot_duration)
            play_audio(tone)
            time.sleep(dot_duration)
        elif symbol == '-':
            tone = generate_tone(dot_duration * 3)
            play_audio(tone)
            time.sleep(dot_duration)
        elif symbol == ' ':
            time.sleep(dot_duration * 3)
        elif symbol == '/':
            time.sleep(dot_duration * 7)
        time.sleep(dot_duration)

if __name__ == "__main__":
    message = input("Enter the message to send in Morse: ")
    morse_code = text_to_morse(message)
    print(f"Sending Morse: {morse_code}")
    play_morse(morse_code)
