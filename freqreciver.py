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
FREQ_TOLERANCE = 50  # Allowed deviation in Hz
THRESHOLD = 0.02  # Amplitude threshold for detecting signals

# Function to detect dominant frequency in signal using FFT
def detect_frequency(audio_data, sample_rate=44100):
    fft_result = np.fft.fft(audio_data)
    frequencies = np.fft.fftfreq(len(fft_result), d=1/sample_rate)

    # Get the peak frequency
    magnitude = np.abs(fft_result)
    peak_index = np.argmax(magnitude)
    peak_frequency = abs(frequencies[peak_index])

    return peak_frequency

# Detect Morse signals (dots and dashes based on frequency)
def detect_morse_signal(audio_data, sample_rate=44100):
    morse_code = []

    # Convert amplitude to binary (1 = signal, 0 = silence)
    binary_signal = np.where(audio_data > THRESHOLD, 1, 0)

    # Detect signal transitions
    transitions = np.diff(binary_signal)
    start_indices = np.where(transitions == 1)[0]
    end_indices = np.where(transitions == -1)[0]

    # Ensure start and end indices align
    if len(end_indices) > 0 and start_indices[0] > end_indices[0]:
        end_indices = end_indices[1:]
    if len(start_indices) > len(end_indices):
        start_indices = start_indices[:-1]

    for start, end in zip(start_indices, end_indices):
        segment = audio_data[start:end]
        detected_frequency = detect_frequency(segment, sample_rate)

        # Classify based on frequency
        if (DOT_FREQUENCY - FREQ_TOLERANCE) < detected_frequency < (DOT_FREQUENCY + FREQ_TOLERANCE):
            morse_code.append(".")  # Dot
        elif (DASH_FREQUENCY - FREQ_TOLERANCE) < detected_frequency < (DASH_FREQUENCY + FREQ_TOLERANCE):
            morse_code.append("-")  # Dash

    return "".join(morse_code)

# Decode Morse Code into text
def morse_to_text(morse_code):
    return "".join(MORSE_CODE_DICT_REV.get(morse_code, "?"))

# Record audio and decode Morse code
def receive_morse(duration=10):
    print(f"Listening for Morse Code for {duration} seconds...")

    recording = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='float32')
    sd.wait()

    morse_code = detect_morse_signal(recording.flatten())
    print(f"Detected Morse Code: {morse_code}")
    decoded_text = morse_to_text(morse_code)
    print(f"Decoded Message: {decoded_text}")

# Start Morse code receiver
receive_morse(duration=10)
