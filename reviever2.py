import numpy as np
import sounddevice as sd
import queue
import threading
from scipy.signal import find_peaks

MORSE_CODE_REVERSED = { 
    '.-':'A', '-...':'B', '-.-.':'C', '-..':'D', '.':'E',
    '..-.':'F', '--.':'G', '....':'H', '..':'I', '.---':'J',
    '-.-':'K', '.-..':'L', '--':'M', '-.':'N', '---':'O',
    '.--.':'P', '--.-':'Q', '.-.':'R', '...':'S', '-':'T',
    '..-':'U', '...-':'V', '.--':'W', '-..-':'X', '-.--':'Y',
    '--..':'Z', '-----':'0', '.----':'1', '..---':'2',
    '...--':'3', '....-':'4', '.....':'5', '-....':'6',
    '--...':'7', '---..':'8', '----.':'9', '--..--':',',
    '.-.-.-':'.', '..--..':'?', '-..-.':'/', '-....-':'-',
    '-.--.':'(', '-.--.-':')'
}

samplerate = 44100
threshold = 0.02  # Adjust as needed based on your audio levels
q = queue.Queue()

def audio_callback(indata, frames, time, status):
    q.put(indata.copy())

def decode_stream():
    buffer = np.array([], dtype='float32')
    symbols = ''
    morse_message = ''

    while True:
        data = q.get()
        buffer = np.concatenate((buffer, data.flatten()))

        if len(buffer) >= samplerate:
            amplitude = np.abs(buffer)
            peaks, _ = find_peaks(amplitude, height=threshold, distance=500)
            times = peaks / samplerate

            if len(times) > 1:
                intervals = np.diff(times)
                for interval in intervals:
                    if interval < 0.15:
                        symbols += '.'
                    elif interval < 0.35:
                        symbols += '-'
                    elif interval < 1.0:
                        morse_message += MORSE_CODE_REVERSED.get(symbols, '')
                        symbols = ''
                    else:
                        morse_message += MORSE_CODE_REVERSED.get(symbols, '') + ' '
                        symbols = ''

                if morse_message:
                    print(f"Decoded message: {morse_message.strip()}")
                    morse_message = ''

            buffer = np.array([], dtype='float32')

if __name__ == "__main__":
    print("Starting Morse Code Receiver (Listening continuously)...")
    stream = sd.InputStream(callback=audio_callback, channels=1, samplerate=samplerate)
    with stream:
        decode_thread = threading.Thread(target=decode_stream)
        decode_thread.start()
        decode_thread.join()
