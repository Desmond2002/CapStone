import pyaudio
import numpy as np
import time
from scipy.signal import butter, lfilter

# Debugging function
def debug_log(message):
    print(f"[DEBUG] {message}")

# Morse Code dictionary
MORSE_CODE_DICT = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z', '-----': '0', '.----': '1', '..---': '2', '...--': '3',
    '....-': '4', '.....': '5', '-....': '6', '--...': '7', '---..': '8',
    '----.': '9'
}

# Audio Processing Parameters
SAMPLE_RATE = 44100  # Standard audio sample rate
THRESHOLD = 2500  # Increased threshold to filter speech noise
MIN_SIGNAL_DURATION = 0.1  # Ignore signals shorter than this (prevents speech artifacts)
DOT_DURATION = 0.15  # Adjusted for longer dots
DASH_DURATION = 0.4  # Adjusted for longer dashes
SYMBOL_SPACE = 0.1  # Space between symbols
LETTER_SPACE = 0.3  # Space between letters
WORD_SPACE = 0.6  # Space between words

# Band-Pass Filter Configuration
LOWCUT = 600  # Morse code tones are usually 600 Hz - 1000 Hz
HIGHCUT = 1000  # Cut frequencies outside this range
FILTER_ORDER = 5  # Order of the filter

# Initialize PyAudio
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE, input=True, frames_per_buffer=1024)

def butter_bandpass(lowcut, highcut, fs, order=5):
    """Design a band-pass filter."""
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return b, a

def apply_bandpass_filter(data, lowcut=LOWCUT, highcut=HIGHCUT, fs=SAMPLE_RATE, order=FILTER_ORDER):
    """Apply a band-pass filter to remove unwanted frequencies (e.g., speech noise)."""
    b, a = butter_bandpass(lowcut, highcut, fs, order)
    return lfilter(b, a, data)

def detect_signal():
    """ Detects audio signals and translates them to Morse Code. """
    debug_log("Listening for Morse Code...")
    morse_sequence = ""
    last_signal_time = time.time()

    while True:
        data = np.frombuffer(stream.read(1024, exception_on_overflow=False), dtype=np.int16)
        filtered_data = apply_bandpass_filter(data)  # Apply band-pass filter
        amplitude = np.max(np.abs(filtered_data))  # Measure the filtered signal strength

        if amplitude > THRESHOLD:  # Detected a strong Morse signal
            signal_start = time.time()
            while amplitude > THRESHOLD:  # Keep listening while the signal is strong
                data = np.frombuffer(stream.read(1024, exception_on_overflow=False), dtype=np.int16)
                filtered_data = apply_bandpass_filter(data)
                amplitude = np.max(np.abs(filtered_data))

            signal_duration = time.time() - signal_start

            # Ignore speech spikes (too short to be Morse code)
            if signal_duration < MIN_SIGNAL_DURATION:
                debug_log(f"Ignored short noise: {signal_duration:.3f}s")
                continue

            debug_log(f"Detected signal of duration: {signal_duration:.2f} sec")

            if signal_duration < DOT_DURATION:
                morse_sequence += "."  # Dot detected
            elif signal_duration >= DASH_DURATION:
                morse_sequence += "-"  # Dash detected

            last_signal_time = time.time()  # Reset last signal time
        
        else:
            silence_duration = time.time() - last_signal_time

            # Process the Morse sequence based on different silence lengths
            if silence_duration > SYMBOL_SPACE and morse_sequence:
                if silence_duration > WORD_SPACE:
                    debug_log(f"Morse Sequence Detected: {morse_sequence} (Word End)")
                    decoded_char = MORSE_CODE_DICT.get(morse_sequence, "?")
                    print(decoded_char, end=" ", flush=True)  # Space for word separation
                    morse_sequence = ""  # Reset for next word
                elif silence_duration > LETTER_SPACE:
                    debug_log(f"Morse Sequence Detected: {morse_sequence} (Letter End)")
                    decoded_char = MORSE_CODE_DICT.get(morse_sequence, "?")
                    print(decoded_char, end="", flush=True)  # No space for letters
                    morse_sequence = ""  # Reset for next letter

                last_signal_time = time.time()  # Reset time

try:
    detect_signal()
except KeyboardInterrupt:
    debug_log("Stopping receiver...")
finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
