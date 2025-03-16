import numpy as np
import scipy.signal as signal
import pyaudio
import queue
import threading

# Constants
MARK_FREQ = 1200  # Hz
SPACE_FREQ = 2200  # Hz
BAUD_RATE = 1200  # Bits per second
SAMPLE_RATE = 44100  # Audio sampling rate
BUFFER_SIZE = 1024  # Buffer for real-time processing

# Pre-emphasis filter coefficients
PRE_EMPHASIS_COEFFS = [1, -0.95]

# Band-pass filter design
def design_bandpass_filter(center_freq, bandwidth, num_taps, sample_rate):
    nyquist = 0.5 * sample_rate
    low = (center_freq - bandwidth / 2) / nyquist
    high = (center_freq + bandwidth / 2) / nyquist
    return signal.firwin(num_taps, [low, high], pass_zero=False)

# Hilbert Transform for quadrature demodulation
def hilbert_transform(sig):
    analytic_signal = signal.hilbert(sig)
    return np.imag(analytic_signal)

# AFSK Demodulation
def afsk_demodulate(received_signal):
    # Apply pre-emphasis filter
    emphasized_signal = signal.lfilter(PRE_EMPHASIS_COEFFS, 1, received_signal)

    # Generate quadrature component
    quadrature_signal = hilbert_transform(emphasized_signal)

    # Band-pass filtering for mark & space
    mark_filter = design_bandpass_filter(MARK_FREQ, 400, 101, SAMPLE_RATE)
    space_filter = design_bandpass_filter(SPACE_FREQ, 400, 101, SAMPLE_RATE)

    mark_signal = signal.lfilter(mark_filter, 1, emphasized_signal)
    space_signal = signal.lfilter(space_filter, 1, emphasized_signal)

    # Envelope detection
    mark_envelope = np.abs(signal.hilbert(mark_signal))
    space_envelope = np.abs(signal.hilbert(space_signal))

    # Bit detection
    bitstream = []
    samples_per_bit = SAMPLE_RATE // BAUD_RATE
    for i in range(0, len(received_signal), samples_per_bit):
        mark_power = np.sum(mark_envelope[i:i + samples_per_bit])
        space_power = np.sum(space_envelope[i:i + samples_per_bit])
        bitstream.append(1 if mark_power > space_power else 0)

    return bitstream

# Convert bitstream to text
def bitstream_to_text(bitstream):
    chars = []
    for i in range(0, len(bitstream), 8):
        byte = bitstream[i:i + 8]
        if len(byte) == 8:
            chars.append(chr(int(''.join(map(str, byte)), 2)))
    return ''.join(chars)

# Real-time AFSK receiver function
def real_time_receiver():
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=BUFFER_SIZE)
    
    print("Listening for incoming AFSK signals... Press Ctrl+C to stop.")

    try:
        while True:
            # Read incoming audio
            audio_data = np.frombuffer(stream.read(BUFFER_SIZE, exception_on_overflow=False), dtype=np.int16)
            audio_signal = audio_data / 32768.0  # Normalize to [-1,1]

            # Demodulate AFSK signal
            bitstream = afsk_demodulate(audio_signal)

            # Convert bits to text and print live output
            message = bitstream_to_text(bitstream)
            if message:
                print("Received:", message, flush=True, end="")

    except KeyboardInterrupt:
        print("\nStopping receiver.")
        stream.stop_stream()
        stream.close()
        p.terminate()

# Run the real-time receiver
if __name__ == "__main__":
    real_time_receiver()
