import numpy as np
import sounddevice as sd
import time
import math

# Morse Code Dictionary (for decoding)
MORSE_CODE_DICT_REV = {v: k for k, v in {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.',
    'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---',
    'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---',
    'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
    'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--',
    'Z': '--..', '0': '-----', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..',
    '9': '----.', ' ': ' '
}.items()}

# Function to detect whether the audio signal is a dot or a dash
def detect_signal(audio_chunk, threshold=0.05, sample_rate=44100, dot_duration=0.1):
    # Calculate the RMS (root mean square) to detect signal strength
    rms = np.sqrt(np.mean(np.square(audio_chunk)))
    
    # If the RMS value is above threshold, we assume it's a signal (beep)
    if rms > threshold:
        # Calculate the length of the signal to determine dot or dash
        duration = len(audio_chunk) / sample_rate
        if duration < dot_duration:
            return '.'  # Short beep -> dot
        else:
            return '-'  # Long beep -> dash
    else:
        return None  # No signal (silence)

# Decode the audio signals into Morse code
def decode_morse_audio(sample_rate=44100, duration=3, threshold=0.05, dot_duration=0.1):
    # Record audio from the microphone for a specific duration
    print("Listening for Morse code...")
    audio_data = sd.rec(int(sample_rate * duration), samplerate=sample_rate, channels=1, dtype='float32')
    sd.wait()
    
    # Process audio to detect Morse signals
    morse_code = []
    chunk_size = int(sample_rate * dot_duration)  # Size of each audio chunk representing a dot
    for i in range(0, len(audio_data), chunk_size):
        chunk = audio_data[i:i + chunk_size]
        signal = detect_signal(chunk, threshold, sample_rate, dot_duration)
        if signal:
            morse_code.append(signal)
        else:
            morse_code.append(' ')  # Silence between signals
            
    morse_code = ''.join(morse_code)
    print(f"Detected Morse Code: {morse_code}")
    return morse_code

# Translate Morse Code into text
def morse_to_text(morse_code):
    words = morse_code.split('   ')  # Morse code for space between words
    text = []
    for word in words:
        chars = word.split()  # Morse code for a single character
        decoded_word = ''.join(MORSE_CODE_DICT_REV.get(char, '') for char in chars)
        text.append(decoded_word)
    return ' '.join(text)

# Main function to receive and decode Morse code
def receive_message():
    morse_code = decode_morse_audio()
    text = morse_to_text(morse_code)
    print(f"Decoded message: {text}")

# Start receiving the message
receive_message()
