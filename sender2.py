import numpy as np
import sounddevice as sd
import time
import argparse

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

# Configuration defaults
DEFAULT_WPM = 10
DEFAULT_FREQ = 600

def calculate_timing(wpm):
    """Calculate timing parameters based on WPM"""
    dot_duration = 1.2 / wpm  # Standard PARIS timing
    return {
        'dot': dot_duration,
        'dash': 3 * dot_duration,
        'symbol_pause': dot_duration,
        'char_pause': 3 * dot_duration,
        'word_pause': 7 * dot_duration
    }

def text_to_morse(text):
    return ' '.join(MORSE_CODE_DICT.get(i.upper(), '') for i in text)

def generate_tone(duration, frequency):
    t = np.linspace(0, duration, int(44100 * duration), False)
    return 0.5 * np.sin(2 * np.pi * frequency * t)

def play_morse(morse_code, timings, frequency):
    for symbol in morse_code:
        if symbol == '.':
            sd.play(generate_tone(timings['dot'], frequency), samplerate=44100)
            sd.wait()
            time.sleep(timings['symbol_pause'])
        elif symbol == '-':
            sd.play(generate_tone(timings['dash'], frequency), samplerate=44100)
            sd.wait()
            time.sleep(timings['symbol_pause'])
        elif symbol == ' ':
            time.sleep(timings['char_pause'])
        elif symbol == '/':
            time.sleep(timings['word_pause'])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Morse Code Sender with Debugging')
    parser.add_argument('--wpm', type=int, default=DEFAULT_WPM, help='Words per minute')
    parser.add_argument('--freq', type=int, default=DEFAULT_FREQ, help='Tone frequency in Hz')
    parser.add_argument('--test', action='store_true', help='Send test pattern')
    args = parser.parse_args()

    timings = calculate_timing(args.wpm)
    message = "PARIS" if args.test else input("Enter message: ")
    
    print(f"Transmitting at {args.wpm} WPM")
    print(f"Timing parameters (ms):")
    print(f"• Dot: {timings['dot']*1000:.1f}ms")
    print(f"• Dash: {timings['dash']*1000:.1f}ms")
    print(f"• Symbol space: {timings['symbol_pause']*1000:.1f}ms")
    print(f"• Character space: {timings['char_pause']*1000:.1f}ms")
    print(f"• Word space: {timings['word_pause']*1000:.1f}ms")

    morse = text_to_morse(message)
    print(f"\nMorse sequence: {morse}")
    play_morse("... / " + morse + " /", timings, args.freq)