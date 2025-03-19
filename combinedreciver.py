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
    '--...': '7', '---..': '8', '----.': '9', '/': ' ', '--..--': ',',
    '.-.-.-': '.', '..--..': '?', '-..-.': '/', '-....-': '-',
    '-.--.': '(', '-.--.-': ')', '': ''
}

samplerate = 44100
threshold = 0.03
dot_duration = 0.1
q = queue.Queue()

def audio_callback(indata, frames, time, status):
    q.put(indata.copy())

def process_received_data(data_str):
    parts = data_str.split(',')
    if len(parts) != 8:
        print(f"Invalid data format: {data_str}")
        return

    try:
        device_id = parts[0]
        recorded_at = parts[1].replace('-', ':', 2).replace('T', 'T')
        output = {
            "device_id": device_id,
            "recorded_at": recorded_at,
            "carbon_monoxide_ppm": float(parts[2]),
            "temperature_celcius": float(parts[3]),
            "pm1_ug_m3": float(parts[4]),
            "pm2_5_ug_m3": float(parts[5]),
            "pm4_ug_m3": float(parts[6]),
            "pm10_ug_m3": float(parts[7])
        }
        print("\nReceived Device Data:")
        print(json.dumps(output, indent=2))
    except (ValueError, IndexError) as e:
        print(f"Error parsing data: {e}")

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
                    in_signal = True
                    signal_start = time.time()
                    if (signal_start - last_time) > 3*dot_duration and current_symbol:
                        message += MORSE_CODE_REVERSED.get(current_symbol, '?')
                        current_symbol = ''
                        print(f"\rCurrent message: {message}", end='')
                    
                elif rms <= threshold and in_signal:
                    in_signal = False
                    signal_duration = time.time() - signal_start
                    last_time = time.time()
                    
                    if signal_duration < 1.5*dot_duration:
                        current_symbol += '.'
                    else:
                        current_symbol += '-'
                        
                elif not in_signal and (time.time() - last_time) > 7*dot_duration:
                    if current_symbol:
                        message += MORSE_CODE_REVERSED.get(current_symbol, '?')
                        current_symbol = ''
                    if message and message[-1] != ' ':
                        message += ' '
                        print(f"\rCurrent message: {message}", end='')

                    if message.strip().endswith('/'):
                        parts = message.strip().split(' / ')
                        if len(parts) >= 2:
                            data_part = parts[1]
                            process_received_data(data_part)
                            message = ''

            except queue.Empty:
                time.sleep(0.01)

if __name__ == "__main__":
    listen_and_decode()