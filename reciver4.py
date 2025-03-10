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
DOT_FREQUENCY = 800  # Frequency for dots (Hz)
DASH_FREQUENCY = 600  # Frequency for dashes (Hz)
DOT_DURATION = 0.1  # Dot duration (seconds)
DASH_DURATION = 0.3  # Dash duration (seconds)
THRESHOLD = 0.02  # Amplitude threshold for detecting signals

# Band-pass filter to isolate specific Morse frequencies
def bandpass_filter(audio_data, lowcut, highcut, sample_rate=44100):
    nyquist = 0.5 * sample_rate
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = signal.butter(4, [low, high], btype='band')
    return signal.lfilter(b, a, audio_data)

# Detect signal transitions and classify dots/dashes
def detect_morse_signal(audio_data, sample_rate=44100):
    # Apply band-pass filters for dot and dash frequencies
    filtered_dots = bandpass_filter(audio_data, DOT_FREQUENCY - 50, DOT_FREQUENCY + 50)
    filtered_dashes = bandpass_filter(audio_data, DASH_FREQUENCY - 50, DASH_FREQUENCY + 50)

    # Convert amplitude to binary (1 = signal, 0 = silence)
    dot_signal = np.where(filtered_dots > THRESHOLD, 1, 0)
    dash_signal = np.where(filtered_dashes > THRESHOLD, 1, 0)

    # Combine dot and dash signals
    binary_signal = np.maximum(dot_signal, dash_signal)

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

        # Detect gaps between letters and words
        if gap > DASH_DURATION * 2:
            morse_code.append("   ")  # Word gap
        elif gap > DOT_DURATION * 1.5:
            morse_code.append(" ")  # Letter gap
        
        # Determine if it's a dot or dash based on frequency and duration
        if np.mean(filtered_dots[start:end]) > np.mean(filtered_dashes[start:end]):
            morse_code.append(".")  # Dot detected
        else:
            morse_code.append("-")  # Dash detected

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
    
    # Record from microphone (3.5mm input)
    recording = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='float32')
    sd.wait()  # Wait for recording to complete

    # Process and decode Morse code
    morse_code = detect_morse_signal(recording.flatten())
    print(f"Detected Morse Code: {morse_code}")

    decoded_text = morse_to_text(morse_code)
    print(f"Decoded Message: {decoded_text}")

# Start Morse code receiver
receive_morse(duration=10)
