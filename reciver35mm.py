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
threshold = 0.02
dot_duration = 0.1
q = queue.Queue()


def audio_callback(indata, frames, t, status):
    q.put(indata.copy())


def listen_and_decode():
    symbols = ''
    decoding_started = False
    in_signal = False
    signal_start = None
    silence_start = None
    waiting_for_first_pause = True

    print("Listening for Morse messages...")

    while True:
        data = q.get().flatten()
        amplitude = np.abs(data)
        audio_level = np.mean(amplitude)
        current_time = time.time()

        if audio_level > threshold:
            if not in_signal:
                in_signal = True
                signal_start = current_time

                if silence_start:
                    silence_duration = current_time - silence_start

                    if waiting_for_first_pause and silence_duration >= dot_duration * 7:
                        waiting_for_first_pause = False
                        decoding_started = True
                        symbols = ''
                        print("\n--- Decoding started ---")
                    elif not waiting_for_first_pause:
                        if silence_duration >= dot_duration * 7:
                            print(' ', end='', flush=True)  # Word spacing
                        elif silence_duration >= dot_duration * 3:
                            print('', end='', flush=True)  # Letter spacing

            silence_start = None

        else:
            if in_signal:
                in_signal = False
                signal_duration = current_time - signal_start

                if signal_duration < dot_duration * 1.5:
                    symbols += '.'
                else:
                    symbols += '-'

                silence_start = current_time

        # Decode letters correctly only after the first word pause
        if silence_start and decoding_started:
            silence_duration = current_time - silence_start
            if silence_duration >= dot_duration * 3 and symbols:
                char = MORSE_CODE_REVERSED.get(symbols, '')
                symbols = ''
                if char:
                    print(char, end='', flush=True)


if __name__ == "__main__":
    with sd.InputStream(callback=audio_callback, channels=1, samplerate=samplerate, blocksize=int(samplerate * 0.02)):
        listen_and_decode()