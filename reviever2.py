import numpy as np
import sounddevice as sd
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
threshold = 0.02  # Adjust based on your audio levels

duration = 20  # Listen for 20 seconds (adjustable)

def decode_audio(recording, threshold):
    amplitude = np.abs(recording)
    peaks, _ = find_peaks(amplitude, height=threshold, distance=500)
    times = peaks / samplerate
    intervals = np.diff(times)
    
    morse = ''
    symbols = ''
    for interval in intervals:
        if interval < 0.15:
            symbols += '.'
        elif interval < 0.35:
            symbols += '-'
        elif interval < 1.0:
            morse += MORSE_CODE_REVERSED.get(symbols, '') + ''
            symbols = ''
        else:
            morse += MORSE_CODE_REVERSED.get(symbols, '') + ' '
            symbols = ''
    if symbols:
        morse += MORSE_CODE_REVERSED.get(symbols, '')
    return morse

if __name__ == "__main__":
    print("Listening for Morse audio...")
    recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='float32')
    sd.wait()
    recording = recording.flatten()
    decoded_message = decode_audio(recording, threshold)
    print(f"Decoded Morse: {decoded_message}")
