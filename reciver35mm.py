import numpy as np
import sounddevice as sd
import queue
import time
from datetime import datetime

MORSE_CODE_REVERSED = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z', '-----': '0', '.----': '1', '..---': '2',
    '...--': '3', '....-': '4', '.....': '5', '-....': '6',
    '--...': '7', '---..': '8', '----.': '9', 
    '.-.-.-': '.', '-....-': '-', '..--.-': '_', '/': ' ', '': ''
}

samplerate = 44100
threshold = 0.05  # Increased for better detection
dot_duration = 0.1
TIMEOUT = 2.0
q = queue.Queue()

def audio_callback(indata, frames, time, status):
    q.put(indata.copy())

def listen_and_decode():
    current_symbol = ''
    message_buffer = ''
    last_activity = time.time()
    in_signal = False

    with sd.InputStream(callback=audio_callback, channels=1, samplerate=samplerate, blocksize=1024):
        print("Listening for sensor data...")
        while True:
            # Check for message completion timeout
            if (time.time() - last_activity) > TIMEOUT and message_buffer:
                process_message(message_buffer)
                message_buffer = ''
                current_symbol = ''

            try:
                data = q.get_nowait().flatten()
                rms = np.sqrt(np.mean(np.square(data)))
                
                if rms > threshold and not in_signal:
                    in_signal = True
                    signal_start = time.time()
                    if (signal_start - last_activity) > 3*dot_duration and current_symbol:
                        message_buffer += MORSE_CODE_REVERSED.get(current_symbol, '?')
                        current_symbol = ''
                        last_activity = time.time()
                        
                elif rms <= threshold and in_signal:
                    in_signal = False
                    signal_duration = time.time() - signal_start
                    last_activity = time.time()
                    
                    if signal_duration < 1.5*dot_duration:
                        current_symbol += '.'
                    else:
                        current_symbol += '-'
                        
                elif not in_signal and (time.time() - last_activity) > 7*dot_duration:
                    if current_symbol:
                        message_buffer += MORSE_CODE_REVERSED.get(current_symbol, '?')
                        current_symbol = ''
                    if message_buffer and message_buffer[-1] != ' ':
                        message_buffer += ' '
                    last_activity = time.time()

            except queue.Empty:
                time.sleep(0.01)

def process_message(raw_message):
    try:
        # Clean the message by removing primer/extra characters
        clean_message = raw_message.replace('...', '').replace('S', '').replace('I', '').strip()
        parts = clean_message.split()
        
        if len(parts) != 7:
            print(f"Invalid message length: {len(parts)} parts")
            return

        device_num = parts[0]
        co = parts[1]
        temp = parts[2]
        pm1 = parts[3]
        pm25 = parts[4]
        pm4 = parts[5]
        pm10 = parts[6]

        print(f"\n\n=== Data Received ===")
        print(f"Device: {device_num}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Carbon Monoxide: {co} ppm")
        print(f"Temperature: {temp} °C")
        print(f"PM1: {pm1} µg/m³")
        print(f"PM2.5: {pm25} µg/m³")
        print(f"PM4: {pm4} µg/m³")
        print(f"PM10: {pm10} µg/m³")
        print("=====================")

    except Exception as e:
        print(f"\nError processing message: {str(e)}")
        print(f"Raw data: {raw_message}")

if __name__ == "__main__":
    listen_and_decode()