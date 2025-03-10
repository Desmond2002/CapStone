import pyaudio
import numpy as np
import time
from scipy.fftpack import fft
import threading

# Morse Code dictionary (reversed for decoding)
MORSE_TO_TEXT = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z', '-----': '0', '.----': '1', '..---': '2', '...--': '3',
    '....-': '4', '.....': '5', '-....': '6', '--...': '7', '---..': '8',
    '----.': '9', '/': ' '
}

# Configuration
CHUNK = 1024  # Number of audio frames per buffer
RATE = 44100  # Audio sampling rate
DOT_FREQUENCY = 800  # Expected frequency for dots (Hz)
DASH_FREQUENCY = 600  # Expected frequency for dashes (Hz)
FREQUENCY_TOLERANCE = 50  # Tolerance range for frequency detection (Hz)
AMPLITUDE_THRESHOLD = 0.01  # Minimum amplitude to detect a signal
SILENCE_THRESHOLD = 0.7  # Time threshold to detect end of a character (seconds)
LETTER_THRESHOLD = 1.5  # Time threshold to detect end of a word (seconds)

# State variables
current_morse = ""
current_word = ""
decoded_text = ""
last_signal_time = 0
is_receiving = True

def debug_log(message):
    print(f"[DEBUG] {message}")

def detect_frequency(audio_data, rate=RATE):
    """Detect the dominant frequency in the audio data"""
    if np.max(np.abs(audio_data)) < AMPLITUDE_THRESHOLD:
        return 0  # No significant audio detected
    
    # Apply windowing
    windowed_data = audio_data * np.hamming(len(audio_data))
    
    # Compute FFT
    fft_data = fft(windowed_data)
    fft_data = np.abs(fft_data[:len(fft_data)//2])
    
    # Find the peak frequency
    peak_index = np.argmax(fft_data)
    peak_freq = peak_index * rate / len(audio_data)
    
    # Get the amplitude of the peak
    peak_amplitude = np.max(fft_data) / len(audio_data)
    
    debug_log(f"Peak frequency: {peak_freq:.1f} Hz, Amplitude: {peak_amplitude:.6f}")
    
    # Return the frequency if it's above the amplitude threshold
    if peak_amplitude > AMPLITUDE_THRESHOLD:
        return peak_freq
    return 0

def interpret_morse_symbol(frequency):
    """Convert a detected frequency to a Morse code symbol"""
    if abs(frequency - DOT_FREQUENCY) <= FREQUENCY_TOLERANCE:
        return "."
    elif abs(frequency - DASH_FREQUENCY) <= FREQUENCY_TOLERANCE:
        return "-"
    return None

def decode_morse():
    """Decode the current Morse code sequence"""
    global current_morse, current_word, decoded_text
    
    if current_morse in MORSE_TO_TEXT:
        letter = MORSE_TO_TEXT[current_morse]
        current_word += letter
        debug_log(f"Decoded: {current_morse} -> {letter}")
    else:
        if current_morse:
            debug_log(f"Unknown Morse sequence: {current_morse}")
    
    current_morse = ""

def check_timing():
    """Check for letter and word boundaries based on timing"""
    global current_morse, current_word, decoded_text, last_signal_time
    
    while is_receiving:
        current_time = time.time()
        
        # If there's an ongoing morse sequence and it's been silent for SILENCE_THRESHOLD
        if current_morse and (current_time - last_signal_time) > SILENCE_THRESHOLD:
            debug_log(f"Letter break detected. Decoding: {current_morse}")
            decode_morse()
        
        # If there's an ongoing word and it's been silent for LETTER_THRESHOLD
        if current_word and (current_time - last_signal_time) > LETTER_THRESHOLD:
            debug_log(f"Word complete: {current_word}")
            decoded_text += current_word + " "
            print(f"Current message: {decoded_text}")
            current_word = ""
        
        time.sleep(0.1)  # Check timing every 100ms

def audio_callback(in_data, frame_count, time_info, status):
    """Callback function for processing audio data"""
    global current_morse, last_signal_time
    
    audio_data = np.frombuffer(in_data, dtype=np.float32)
    frequency = detect_frequency(audio_data)
    
    if frequency > 0:
        symbol = interpret_morse_symbol(frequency)
        if symbol:
            current_morse += symbol
            last_signal_time = time.time()
            debug_log(f"Detected symbol: {symbol}, Current sequence: {current_morse}")
    
    return (in_data, pyaudio.paContinue)

def main():
    """Main function to set up and run the Morse code receiver"""
    global is_receiving
    
    print("Morse Code Receiver Starting...")
    print(f"Listening for dots at {DOT_FREQUENCY}Hz and dashes at {DASH_FREQUENCY}Hz")
    
    # Start the timing check thread
    timing_thread = threading.Thread(target=check_timing)
    timing_thread.daemon = True
    timing_thread.start()
    
    # Initialize PyAudio
    p = pyaudio.PyAudio()
    
    try:
        # Open audio stream
        stream = p.open(format=pyaudio.paFloat32,
                        channels=1,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK,
                        stream_callback=audio_callback)
        
        print("Listening... Press Ctrl+C to stop.")
        stream.start_stream()
        
        # Keep running until interrupted
        while stream.is_active():
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        is_receiving = False
        if 'stream' in locals():
            stream.stop_stream()
            stream.close()
        p.terminate()
        print(f"Final decoded message: {decoded_text}")

if __name__ == "__main__":
    main()