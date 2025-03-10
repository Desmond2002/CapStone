import numpy as np
import sounddevice as sd
import time

# Audio Settings
SAMPLE_RATE = 44100  # High-quality audio
FREQUENCY = 800  # Frequency of beep (800Hz)
DOT_DURATION = 0.15  # 150ms for a dot
GAP_DURATION = 0.15  # 150ms silence between dots

def generate_tone(duration, frequency=FREQUENCY):
    """Generate a sine wave tone for the given duration and frequency."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    wave = 0.5 * np.sin(2 * np.pi * frequency * t)  # 50% volume
    return wave

def send_dot():
    """Send a Morse dot as a beep through the 3.5mm jack."""
    print("[SENDING] Dot")

    # Generate the dot sound
    tone = generate_tone(DOT_DURATION)
    sd.play(tone, samplerate=SAMPLE_RATE)
    sd.wait()

    # Add a silent gap after the dot
    time.sleep(GAP_DURATION)

if __name__ == "__main__":
    print("Sending dots continuously... Press Ctrl+C to stop.")
    try:
        while True:
            send_dot()
    except KeyboardInterrupt:
        print("\nTransmission stopped.")
