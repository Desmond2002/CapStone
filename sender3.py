import numpy as np
import scipy.signal as signal
import pyaudio

# Constants
MARK_FREQ = 1200  # Hz
SPACE_FREQ = 2200  # Hz
BAUD_RATE = 1200  # bits per second
SAMPLE_RATE = 44100  # Hz
AMPLITUDE = 0.5  # Signal amplitude

# AFSK Modulation using CPFSK
def afsk_modulate(bitstream):
    samples_per_bit = SAMPLE_RATE // BAUD_RATE
    time = np.arange(samples_per_bit) / SAMPLE_RATE
    signal_out = np.array([])
    phase = 0  # Phase accumulator

    for bit in bitstream:
        freq = MARK_FREQ if bit == 1 else SPACE_FREQ
        phase_increment = 2 * np.pi * freq / SAMPLE_RATE
        bit_signal = AMPLITUDE * np.sin(phase + phase_increment * np.arange(samples_per_bit))
        signal_out = np.concatenate((signal_out, bit_signal))
        phase += phase_increment * samples_per_bit  # Maintain phase continuity

    return signal_out

# Convert text to bitstream
def text_to_bitstream(text):
    bitstream = []
    for char in text:
        bits = bin(ord(char))[2:].zfill(8)  # Convert to 8-bit binary
        bitstream.extend([int(bit) for bit in bits])
    return bitstream

# Play audio signal through output
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

# Main function for sending
if __name__ == "__main__":
    message = input("Enter message to send: ")
    bitstream = text_to_bitstream(message)
    modulated_signal = afsk_modulate(bitstream)

    print("Transmitting...")
    play_signal(modulated_signal)
    print("Transmission complete.")
