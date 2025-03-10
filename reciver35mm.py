import numpy as np
import sounddevice as sd
import scipy.signal as signal
import time

# Morse Code Dictionary (Reverse Lookup)
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

# Constants
SAMPLE_RATE = 44100  # Standard audio sample rate
MORSE_FREQUENCY = 1000  # Morse tone frequency (Hz)
DOT_DURATION = 0.1  # Dot duration (seconds)
THRESHOLD = 0.02  # Amplitude threshold for detecting signals

# Band-pass filter to isolate Morse frequency (1000 Hz)
def bandpass_filter(audio_data, lowcut=900, highcut=1100, sample_rate=44100):
    nyquist = 0.5 * sample_rate
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = signal.butter(4, [low, high], btype='band')
    return signal.lfilter(b, a, audio_data)

# Detect signal transitions and classify dots/dashes
def detect_morse_signal(audio_data, sample_rate=44100):
    filtered_audio = bandpass_filter(audio_data)

    # Convert amplitude to binary (1 = signal, 0 = silence)
    binary_signal = np.where(filtered_audio > THRESHOLD, 1, 0)

    # Detect signal transitions
    transitions = np.diff(binary_signal)
    start_indices = np.where(transitions == 1)[0]
    end_indices = np.where(transitions == -1)[0]

    # Ensure start and end indices are aligned
    if len(end_indices) > 0 and start_indices[0] > end_indices[0]:
        end_indices = end_indices[1:]  # Drop first end if it has no start
    if len(start_indices) > len(end_indices):
        start_indices = start_indices[:-1]  # Drop last start if it has no end

    # Convert tone durations to Morse symbols
    morse_code = []
    previous_end = 0

    for start, end in zip(start_indices, end_indices):
        duration = (end - start) / sample_rate
        gap = (start - previous_end) / sample_rate

        if gap > DOT_DURATION * 3:
            morse_code.append("   ")  # Word gap
        elif gap > DOT_DURATION * 1.5:
            morse_code.append(" ")  # Letter gap
        
        if duration < DOT_DURATION * 1.5:
            morse_code.append(".")
        else:
            morse_code.append("-")

        previous_end = end

    return "".join(morse_code)

# Decode Morse Code into text
def morse_to_text(morse_code):
    words = morse_code.split("   ")  # Word gap = three spaces
    decoded_text = []

    for word in words:
        letters = word.split()  # Letter gap = one space
        decoded_word = "".join(MORSE_CODE_DICT_REV.get(letter, "?") for letter in letters)
        decoded_text.append(decoded_word)

    return " ".join(decoded_text)

# Record audio and decode Morse code
def receive_morse(duration=10):
    print(f"Listening for Morse Code for {duration} seconds...")
    
    # Record from microphone
    recording = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='float32')
    sd.wait()  # Wait for recording to complete

    # Process and decode Morse code
    morse_code = detect_morse_signal(recording.flatten())
    print(f"Detected Morse Code: {morse_code}")

    decoded_text = morse_to_text(morse_code)
    print(f"Decoded Message: {decoded_text}")

# Start Morse code receiver
receive_morse(duration=10)
