import pyaudio
import numpy as np
import time
from scipy.signal import butter, lfilter

# Audio Processing Parameters
SAMPLE_RATE = 44100
THRESHOLD = 2500  # Adjust if needed
DOT_DURATION = 0.15  # Expected dot duration
LOWCUT = 600  # Band-pass filter: 600Hz - 1000Hz
HIGHCUT = 1000
FILTER_ORDER = 5

# Initialize PyAudio
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE, input=True, frames_per_buffer=1024)

# Band-Pass Filter
def butter_bandpass(lowcut, highcut, fs, order=5):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return b, a

def apply_bandpass_filter(data, lowcut=LOWCUT, highcut=HIGHCUT, fs=SAMPLE_RATE, order=FILTER_ORDER):
    b, a = butter_bandpass(lowcut, highcut, fs, order)
    return lfilter(b, a, data)

def detect_signal():
    """Detects Morse dots and logs their durations."""
    print("Listening for Morse dots... Press Ctrl+C to stop.")
    dot_log = []

    while True:
        data = np.frombuffer(stream.read(1024, exception_on_overflow=False), dtype=np.int16)
        filtered_data = apply_bandpass_filter(data)
        amplitude = np.max(np.abs(filtered_data))

        if amplitude > THRESHOLD:
            start_time = time.time()
            print("[DETECTED] Dot Start")

            # Wait for dot to end
            while amplitude > THRESHOLD:
                data = np.frombuffer(stream.read(1024, exception_on_overflow=False), dtype=np.int16)
                filtered_data = apply_bandpass_filter(data)
                amplitude = np.max(np.abs(filtered_data))

            end_time = time.time()
            duration = end_time - start_time
            print(f"[LOGGED] Dot Duration: {duration:.3f} sec")

            dot_log.append(duration)

            time.sleep(0.1)  # Prevent detecting the same dot multiple times

try:
    detect_signal()
except KeyboardInterrupt:
    print("\nStopped listening.")
finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
