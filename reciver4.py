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
WORD_GAP = 0.7  # Time threshold for word spacing
THRESHOLD = 0.02  # Dynamic threshold (may need tuning)

# Fast Fourier Transform (FFT) function to detect frequencies
def detect_frequency(audio_data, sample_rate=44100):
    fft_result = np.fft.fft(audio_data)
    frequencies = np.fft.fftfreq(len(fft_result), d=1/sample_rate)

    # Get the peak frequency
    magnitude = np.abs(fft_result)
    peak_index = np.argmax(magnitude)
    peak_frequency = abs(frequencies[peak_index])

    return peak_frequency

# Detect Morse signals (dots and dashes)
def detect_morse_signal(audio_data, sample_rate=44100):
    morse_code = []
    previous_end = 0

    # Convert amplitude to binary (1 = signal, 0 = silence)
    binary_signal = np.where(audio_data > THRESHOLD, 1, 0)

    # Detect signal transitions
    transitions = np.diff(binary_signal)
    start_indices = np.where(transitions == 1)[0]
    end_indices = np.where(transitions == -1)[0]

    # Ensure start and end indices align
    if len(end_indices) > 0 and start_indices[0] > end_indices[0]:
        end_indices = end_indices[1:]  # Drop first end if it has no start
    if len(start_indices) > len(end_indices):
        start_indices = start_indices[:-1]  # Drop last start if it has no end

    for start, end in zip(start_indices, end_indices):
        duration = (end - start) / sample_rate
        gap = (start - previous_end) / sample_rate

        # Use FFT to identify frequency
        segment = audio_data[start:end]
        detected_frequency = detect_frequency(segment, sample_rate)

        # Identify signal as dot or dash based on frequency & duration
        if 750 < detected_frequency < 850 and duration <= 0.2:
            morse_code.append(".")  # Dot
        elif 550 < detected_frequency < 650 and duration > 0.2:
            morse_code.append("-")  # Dash
        
        # Detect spacing
        if gap > WORD_GAP:
            morse_code.append("   ")  # Word gap
        elif gap > DOT_DURATION * 1.5:
            morse_code.append(" ")  # Letter gap

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
