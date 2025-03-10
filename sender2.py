import pyaudio
import numpy as np
import time

# Morse Code Dictionary
MORSE_CODE_DICT = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.',
    'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---',
    'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---',
    'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
    'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--',
    'Z': '--..', '0': '-----', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..',
    '9': '----.', ' ': '/'
}

# Morse Timing
DOT_DURATION = 0.2   # 200ms for a dot
DASH_DURATION = 0.6  # 600ms for a dash
SYMBOL_GAP = 0.2     # Gap between symbols
LETTER_GAP = 0.4     # Gap between letters
WORD_GAP = 0.8       # Gap between words

# Audio Configuration
SAMPLE_RATE = 44100  # CD quality audio
TONE_FREQUENCY = 1000  # Frequency of Morse beep (Hz)
VOLUME = 0.5  # Audio volume (0.0 to 1.0)

# Initialize PyAudio
p = pyaudio.PyAudio()

def generate_tone(frequency, duration):
    """Generate a sine wave tone."""
    samples = (np.sin(2 * np.pi * np.arange(SAMPLE_RATE * duration) * frequency / SAMPLE_RATE)).astype(np.float32)
    return VOLUME * samples

def play_sound(frequency, duration):
    """Play a sound through the 3.5mm jack."""
    stream = p.open(format=pyaudio.paFloat32, channels=1, rate=SAMPLE_RATE, output=True)
    tone = generate_tone(frequency, duration)
    stream.write(tone.tobytes())
    stream.stop_stream()
    stream.close()

def text_to_morse(text):
    """Convert text to Morse code."""
    return ' '.join(MORSE_CODE_DICT[char] for char in text.upper() if char in MORSE_CODE_DICT)

def send_message(text):
    """Send Morse code as audio pulses."""
    print(f"Sending: {text}")
    morse_code = text_to_morse(text)

    for symbol in morse_code:
        if symbol == '.':
            play_sound(TONE_FREQUENCY, DOT_DURATION)  # Dot sound
            time.sleep(SYMBOL_GAP)
        elif symbol == '-':
            play_sound(TONE_FREQUENCY, DASH_DURATION)  # Dash sound
            time.sleep(SYMBOL_GAP)
        elif symbol == ' ':
            time.sleep(LETTER_GAP)  # Letter pause
        elif symbol == '/':
            time.sleep(WORD_GAP)  # Word pause

    print("Message sent.")

if __name__ == "__main__":
    send_message("SOS")  # Example transmission
    p.terminate()  # Clean up PyAudio
