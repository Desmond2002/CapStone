import pyaudio
import numpy as np
import time
from scipy.signal import butter, lfilter, find_peaks

# Debugging function
def debug_log(message):
    print(f"[DEBUG] {message}")

# Morse Code dictionary (reverse lookup for decoding)
MORSE_CODE_DICT = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z', '-----': '0', '.----': '1', '..---': '2', '...--': '3',
    '....-': '4', '.....': '5', '-....': '6', '--...': '7', '---..': '8',
    '----.': '9', '/': ' '
}

# Audio processing settings
SAMPLE_RATE = 44100  # Audio sample rate (Hz)
CHUNK_SIZE = 1024  # Number of audio frames per buffer
FREQUENCY_TARGET = 1000  # Expected Morse frequency (Hz)
FREQUENCY_TOLERANCE = 200  # Allow +/- 200Hz around target (800-1200Hz)
DOT_THRESHOLD = 0.5  # Dots are considered if less than 0.5 sec
DASH_THRESHOLD = 1.5  # Dashes are considered if less than 1.5 sec
TONE_MIN_DURATION = 0.05  # Minimum tone duration (50ms) to avoid noise
AMPLITUDE_THRESHOLD = 1000  # Ignore low amplitude signals - increased for better noise rejection
LETTER_PAUSE_THRESHOLD = 2.0  # Time gap between letters
WORD_PAUSE_THRESHOLD = 4.0  # Time gap between words
CONSECUTIVE_SAMPLES_THRESHOLD = 3  # Number of consecutive chunks to confirm a signal

# Signal state tracking
last_signal_end_time = 0
current_letter = ""
current_message = ""
signal_buffer = []  # Buffer to track consecutive signal detections

def init_audio():
    """Initialize the audio stream."""
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=CHUNK_SIZE)
    return p, stream

def bandpass_filter(data, lowcut=FREQUENCY_TARGET-FREQUENCY_TOLERANCE, 
                   highcut=FREQUENCY_TARGET+FREQUENCY_TOLERANCE, fs=SAMPLE_RATE, order=5):
    """Applies a bandpass filter focused on the Morse frequency range."""
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return lfilter(b, a, data)

def detect_tone(data):
    """
    Improved tone detection with FFT analysis and noise rejection.
    Returns (is_tone, power) where power indicates signal strength.
    """
    audio_data = np.frombuffer(data, dtype=np.int16)
    
    # Check if volume is too low before processing
    amplitude = np.max(np.abs(audio_data))
    if amplitude < AMPLITUDE_THRESHOLD:
        return False, 0
    
    # Apply bandpass filter to isolate the target frequency range
    filtered_audio = bandpass_filter(audio_data)
    
    # Calculate FFT
    fft_result = np.abs(np.fft.rfft(filtered_audio))
    freqs = np.fft.rfftfreq(len(filtered_audio), 1/SAMPLE_RATE)
    
    # Find the dominant frequency in our range of interest
    target_range = (freqs >= FREQUENCY_TARGET-FREQUENCY_TOLERANCE) & (freqs <= FREQUENCY_TARGET+FREQUENCY_TOLERANCE)
    if not np.any(target_range):
        return False, 0
        
    # Get the peak in our frequency range
    peak_idx = np.argmax(fft_result[target_range])
    peak_freq = freqs[target_range][peak_idx]
    peak_power = fft_result[target_range][peak_idx]
    
    # Check for significant power in our frequency range
    background_power = np.mean(fft_result[~target_range])
    signal_to_noise = peak_power / (background_power + 1e-10)  # Avoid division by zero
    
    debug_log(f"Peak freq: {peak_freq:.1f}Hz, Power: {peak_power:.1f}, SNR: {signal_to_noise:.1f}")
    
    # Only consider it a tone if SNR is high enough
    return signal_to_noise > 3.0, peak_power

def process_morse_element(element_type):
    """Process a detected Morse element (dot, dash, letter space, word space)."""
    global current_letter, current_message
    
    if element_type == "dot":
        current_letter += "."
        debug_log(f"Dot detected - Current letter: {current_letter}")
    elif element_type == "dash":
        current_letter += "-"
        debug_log(f"Dash detected - Current letter: {current_letter}")
    elif element_type == "letter_space":
        # Translate the current letter
        if current_letter:
            char = MORSE_CODE_DICT.get(current_letter, "?")
            current_message += char
            debug_log(f"Letter complete: {current_letter} -> {char}")
            current_letter = ""
    elif element_type == "word_space":
        # First complete the current letter if any
        if current_letter:
            char = MORSE_CODE_DICT.get(current_letter, "?")
            current_message += char
            debug_log(f"Letter complete: {current_letter} -> {char}")
            current_letter = ""
        
        # Then add a space
        current_message += " "
        debug_log("Word space detected")
    
    # Print the current message state
    debug_log(f"Current message: {current_message}")

def listen_for_morse():
    """Enhanced Morse code listening function with better noise rejection."""
    global last_signal_end_time, current_letter, current_message, signal_buffer
    
    p, stream = init_audio()
    
    debug_log("Listening for Morse Code...")
    
    in_signal = False
    signal_start_time = None
    
    try:
        while True:
            current_time = time.time()
            
            # Check for letter or word completion based on silence
            if not in_signal and current_letter and (current_time - last_signal_end_time > LETTER_PAUSE_THRESHOLD):
                process_morse_element("letter_space")
                
            if not in_signal and (current_time - last_signal_end_time > WORD_PAUSE_THRESHOLD) and current_message and not current_message.endswith(" "):
                process_morse_element("word_space")
            
            # Read audio
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            is_tone, power = detect_tone(data)
            
            # Use a buffer to require consecutive positive samples for more reliable detection
            signal_buffer.append(is_tone)
            if len(signal_buffer) > CONSECUTIVE_SAMPLES_THRESHOLD:
                signal_buffer.pop(0)
                
            # Only consider it a real signal if we have enough consecutive positive detections
            stable_signal = sum(signal_buffer) >= CONSECUTIVE_SAMPLES_THRESHOLD - 1
            
            if stable_signal and not in_signal:
                # Beginning of a tone
                in_signal = True
                signal_start_time = current_time
                debug_log("Signal started")
            
            elif not stable_signal and in_signal:
                # End of a tone
                in_signal = False
                duration = current_time - signal_start_time
                last_signal_end_time = current_time
                
                if duration >= TONE_MIN_DURATION:
                    if duration < DOT_THRESHOLD:
                        process_morse_element("dot")
                    else:
                        process_morse_element("dash")
                else:
                    debug_log(f"Ignoring short noise ({duration:.3f}s)")
                    
            # Display final output if message completed (long pause)
            if current_message and (current_time - last_signal_end_time > WORD_PAUSE_THRESHOLD * 1.5) and current_message[-1] != "\n":
                print(f"DECODED MESSAGE: {current_message}")
                current_message += "\n"  # Mark as printed
                    
    except KeyboardInterrupt:
        debug_log("Stopping Morse receiver...")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    listen_for_morse()