import numpy as np
import sounddevice as sd
import queue
import time
import json

MORSE_CODE_REVERSED = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z', '-----': '0', '.----': '1', '..---': '2',
    '...--': '3', '....-': '4', '.....': '5', '-....': '6',
    '--...': '7', '---..': '8', '----.': '9', '/': ' ', '': '',
    '--..--': ',', '.-.-.-': '.', '..--.-': '_', '-....-': '-'
}

samplerate = 44100
threshold = 0.03
dot_duration = 0.1
q = queue.Queue()

def audio_callback(indata, frames, time, status):
    q.put(indata.copy())

def parse_data(data_str):
    try:
        parts = data_str.split(',')
        return {
            "device_id": parts[0],
            "recorded_at": parts[1],
            "carbon_monoxide_ppm": float(parts[2]),
            "temperature_celcius": float(parts[3]),
            "pm1_ug_m3": float(parts[4]),
            "pm2_5_ug_m3": float(parts[5]),
            "pm4_ug_m3": float(parts[6]),
            "pm10_ug_m3": float(parts[7])
        }
    except Exception as e:
        print(f"Parse error: {e}")
        return None

def listen_and_decode():
    buffer = ''
    current_symbol = ''
    sync_count = 0
    in_signal = False
    receiving_data = False
    signal_start = time.time()  # Initialize timing variables
    last_signal = time.time()

    with sd.InputStream(callback=audio_callback, channels=1, samplerate=samplerate, blocksize=1024):
        print("Listening for Morse code...")
        while True:
            try:
                data = q.get_nowait().flatten()
                rms = np.sqrt(np.mean(np.square(data)))
                current_time = time.time()

                if rms > threshold:
                    if not in_signal:
                        in_signal = True
                        signal_start = current_time
                        last_signal = current_time
                        if not receiving_data:
                            if (current_time - last_signal) > 5*dot_duration:
                                sync_count = 0
                else:
                    if in_signal:
                        in_signal = False
                        signal_duration = current_time - signal_start
                        last_signal = current_time
                        
                        if signal_duration < 1.5*dot_duration:
                            current_symbol += '.'
                        else:
                            current_symbol += '-'

                        if not receiving_data:
                            if current_symbol == '.':
                                sync_count += 1
                                if sync_count >= 6:
                                    receiving_data = True
                                    buffer = ''
                            else:
                                sync_count = 0

                if not in_signal and (current_time - signal_start) > 3*dot_duration:
                    if current_symbol:
                        char = MORSE_CODE_REVERSED.get(current_symbol, '?')
                        buffer += char
                        current_symbol = ''
                        
                        if receiving_data:
                            print(f"\rReceiving: {buffer}", end='')
                            if buffer.endswith('/'):
                                data_str = buffer[:-1].strip()
                                data = parse_data(data_str)
                                if data:
                                    print("\n\nValid Data Received:")
                                    print(json.dumps(data, indent=2))
                                receiving_data = False
                                buffer = ''

                time.sleep(0.001)
                
            except queue.Empty:
                time.sleep(0.01)

if __name__ == "__main__":
    listen_and_decode()