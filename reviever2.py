import numpy as np
import sounddevice as sd
import queue
import time

MORSE_CODE_REVERSED = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z', '-----': '0', '.----': '1', '..---': '2',
    '...--': '3', '....-': '4', '.....': '5', '-....': '6',
    '--...': '7', '---..': '8', '----.': '9', '/': ' '
}

samplerate = 44100
threshold = 0.02  # Adjust based on your mic input
dot_duration = 0.1
q = queue.Queue()


def audio_callback(indata, frames, t, status):
    q.put(indata.copy())


def listen_and_decode():
    symbols = ''
    decoding_started = False
    silence_start = None
    signal_start = None
    print("Listening for Morse messages...")

    while True:
        data = q.get().flatten()
        amplitude = np.abs(data)
        audio_level = np.mean(amplitude)
        current_time = time.time()

        if audio_level > threshold:
            if signal_start is None:
                signal_start = current_time
            silence_start = None
        else:
            if signal_start is not None:
                duration = current_time - signal_start
                signal_start = None

                if duration >= 0.02:  # Filter noise
                    if duration < dot_duration * 1.5:
                        symbols += '.'
                    else:
                        symbols += '-'

                silence_start = current_time

        if silence_start:
            silence_duration = current_time - silence_start

            if silence_duration >= dot_duration * 7:
                if not decoding_started:
                    decoding_started = True
                    symbols = ''
                    print("\n--- Decoding started ---")
                elif symbols:
                    char = MORSE_CODE_REVERSED.get(symbols, '')
                    symbols = ''
                    if char:
                        print(char, end='', flush=True)
                    print(' ', end='', flush=True)

            elif silence_duration >= dot_duration * 3:
                if symbols and decoding_started:
                    char = MORSE_CODE_REVERSED.get(symbols, '')
                    symbols = ''
                    if char:
                        print(char, end='', flush=True)

        if audio_level > threshold:
            if signal_start is None:
                signal_start = current_time
                if silence_start and not decoding_started:
                    silence_duration = current_time - silence_start
                    if silence_duration >= dot_duration * 7:
                        decoding_started = True
                        symbols = ''
                        print("\n--- Decoding started ---")
            silence_start = None
        else:
            if silence_start is None:
                silence_start = current_time


if __name__ == "__main__":
    with sd.InputStream(callback=audio_callback, channels=1, samplerate=samplerate):
        listen_and_decode()