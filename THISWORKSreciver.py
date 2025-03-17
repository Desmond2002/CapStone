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
    '--...': '7', '---..': '8', '----.': '9', '/': ' ', '': ''
}

samplerate = 44100
threshold = 0.03  # Adjust based on your microphone sensitivity
dot_duration = 0.1
q = queue.Queue()

def audio_callback(indata, frames, time, status):
    q.put(indata.copy())

def listen_and_decode():
    current_symbol = ''
    message = ''
    last_time = time.time()
    in_signal = False

    with sd.InputStream(callback=audio_callback, channels=1, samplerate=samplerate, blocksize=1024):
        print("Listening for Morse code...")
        while True:
            try:
                data = q.get_nowait().flatten()
                rms = np.sqrt(np.mean(np.square(data)))
                
                if rms > threshold and not in_signal:
                    # Signal started
                    in_signal = True
                    signal_start = time.time()
                    if (signal_start - last_time) > 3*dot_duration and current_symbol:
                        # New character
                        message += MORSE_CODE_REVERSED.get(current_symbol, '?')
                        current_symbol = ''
                        print(f"\rCurrent message: {message}", end='')
                    
                elif rms <= threshold and in_signal:
                    # Signal ended
                    in_signal = False
                    signal_duration = time.time() - signal_start
                    last_time = time.time()
                    
                    if signal_duration < 1.5*dot_duration:
                        current_symbol += '.'
                    else:
                        current_symbol += '-'
                        
                elif not in_signal and (time.time() - last_time) > 7*dot_duration:
                    # End of word
                    if current_symbol:
                        message += MORSE_CODE_REVERSED.get(current_symbol, '?')
                        current_symbol = ''
                    if message and message[-1] != ' ':
                        message += ' '
                        print(f"\rCurrent message: {message}", end='')

            except queue.Empty:
                time.sleep(0.01)

if __name__ == "__main__":
    listen_and_decode()