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
    waiting_for_sync = True
    waiting_for_message = False
    message = ''
    signal_start = None
    silence_start = None

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

                if duration >= 0.02:
                    if duration < dot_duration * 1.5:
                        if not waiting_for_sync:
                            symbols += '.'
                    else:
                        if not waiting_for_sync:
                            symbols += '-'

                silence_start = current_time

        if silence_start:
            silence_duration = current_time - silence_start

            if waiting_for_sync:
                if silence_duration >= dot_duration * 7:
                    waiting_for_sync = False
                    waiting_for_message = True
                    symbols = ''
                    print("\n--- Sync Detected ---")
            elif waiting_for_message:
                if silence_duration >= dot_duration * 7:
                    waiting_for_message = False
                    if message:
                        print(f"\nDecoded Message: {message}")
                        message = ''  # Reset after full message received
            else:
                if silence_duration >= dot_duration * 3:
                    if symbols:
                        char = MORSE_CODE_REVERSED.get(symbols, '')
                        symbols = ''
                        if char:
                            message += char
                elif silence_duration >= dot_duration * 7:
                    waiting_for_message = True  # Prepare for final decoding pause

        if audio_level > threshold:
            if signal_start is None:
                signal_start = current_time
                silence_start = None
        else:
            if silence_start is None:
                silence_start = current_time


if __name__ == "__main__":
    with sd.InputStream(callback=audio_callback, channels=1, samplerate=samplerate):
        listen_and_decode()
