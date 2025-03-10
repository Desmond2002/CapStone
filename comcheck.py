import numpy as np
import sounddevice as sd

def generate_tone(frequency, duration=1.0, sample_rate=44100):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    signal = np.sin(2 * np.pi * frequency * t)
    return signal * 0.5  # Normalize volume

# Generate a 1000 Hz test tone
tone = generate_tone(1000, duration=2.0)
sd.play(tone, samplerate=44100)
sd.wait()
print("Test tone played.")
