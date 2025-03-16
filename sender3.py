import numpy as np
import pyaudio
from scipy.signal import butter, lfilter

# Constants
MARK_FREQ = 1200  # Hz (bit '1')
SPACE_FREQ = 2200  # Hz (bit '0')
BAUD_RATE = 1200   # Baud rate (bits per second)
SAMPLE_RATE = 44100  # Audio sampling rate
BUFFER_SIZE = 1024  # Audio buffer

# Bandpass Filter
def butter_bandpass(lowcut, highcut, fs, order=5):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def bandpass_filter(data, lowcut, highcut, fs, order=5):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    return lfilter(b, a, data)

# Quadrature Demodulation
def quadrature_demod(samples):
    time = np.arange(len(samples)) / SAMPLE_RATE
    ref_mark = np.exp(-1j * 2 * np.pi * MARK_FREQ * time)
    ref_space = np.exp(-1j * 2 * np.pi * SPACE_FREQ * time)

    demod_mark = np.abs(np.convolve(samples * ref_mark, np.ones(10)/10, mode='same'))
    demod_space = np.abs(np.convolve(samples * ref_space, np.ones(10)/10, mode='same'))

    return demod_mark, demod_space

# Decode AFSK Signal
def afsk_demodulate(samples):
    # Filter signal
    mark_filtered = bandpass_filter(samples, 1000, 1300, SAMPLE_RATE)
    space_filtered = bandpass_filter(samples, 2000, 2500, SAMPLE_RATE)

    # Quadrature detection
    mark_strength, space_strength = quadrature_demod(mark_filtered)

    # Decode bits
    bitstream = []
    for i in range(0, len(mark_strength), SAMPLE_RATE // BAUD_RATE):
        if i + SAMPLE_RATE // BAUD_RATE > len(mark_strength):
            break
        mark_power = np.sum(mark_strength[i:i + SAMPLE_RATE // BAUD_RATE])
        space_power = np.sum(space_strength[i:i + SAMPLE_RATE // BAUD_RATE])

        bit = 1 if mark_power > space_power else 0
        bitstream.append(bit)

    return bitstream

# Convert Bits to Text
def bits_to_text(bits):
    chars = [bits[i:i + 8] for i in range(0, len(bits), 8)]
    return ''.join(chr(int(''.join(map(str, c)), 2)) for c in chars if len(c) == 8)

# Receive AFSK Signal
def record_signal():
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=BUFFER_SIZE)

    print("Listening...")
    frames = []
    try:
        while True:
            data = np.frombuffer(stream.read(BUFFER_SIZE), dtype=np.int16)
            frames.extend(data)
    except KeyboardInterrupt:
        print("\nStopped recording.")
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    return np.array(frames, dtype=np.float32) / 32768.0  # Normalize

if __name__ == "__main__":
    audio_signal = record_signal()
    bitstream = afsk_demodulate(audio_signal)
    message = bits_to_text(bitstream)

    print("\nReceived Message:", message)
