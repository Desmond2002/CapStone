import numpy as np
import pyaudio

# Constants
MARK_FREQ = 1200  # Hz (bit '1')
SPACE_FREQ = 2200  # Hz (bit '0')
BAUD_RATE = 1200  # Baud (bits per second)
SAMPLE_RATE = 44100  # Hz

# NRZI Encoding
def nrzi_encode(bitstream):
    encoded = []
    last_bit = 1  # Start with '1'
    for bit in bitstream:
        if bit == 0:
            last_bit = 1 - last_bit  # Toggle
        encoded.append(last_bit)
    return encoded

# Generate CPFSK Modulated Signal
def afsk_modulate(bits):
    samples_per_bit = SAMPLE_RATE // BAUD_RATE
    time = np.arange(samples_per_bit) / SAMPLE_RATE
    phase = 0  # Phase accumulator
    signal = np.array([])

    # Convert bits using NRZI
    bits = nrzi_encode(bits)

    for bit in bits:
        freq = MARK_FREQ if bit == 1 else SPACE_FREQ
        phase_step = 2 * np.pi * freq / SAMPLE_RATE
        waveform = np.sin(phase + phase_step * np.arange(samples_per_bit))
        phase += phase_step * samples_per_bit  # Maintain phase continuity
        signal = np.concatenate((signal, waveform))

    return signal

# Convert Text to Bits
def text_to_bits(text):
    return [int(bit) for char in text for bit in f"{ord(char):08b}"]

# Play Audio Signal
def play_signal(signal):
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32,
                    channels=1,
                    rate=SAMPLE_RATE,
                    output=True)

    stream.write(signal.astype(np.float32).tobytes())
    stream.stop_stream()
    stream.close()
    p.terminate()

if __name__ == "__main__":
    message = input("Enter message to send: ")
    bits = text_to_bits(message)
    afsk_signal = afsk_modulate(bits)

    print("Transmitting...")
    play_signal(afsk_signal)
