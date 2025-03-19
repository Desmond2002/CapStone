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
threshold = 0.05
dot_duration = 0.1
q = queue.Queue()

def audio_callback(indata, frames, time, status):
    q.put(indata.copy())

def listen_and_decode():
    current_symbol = ''
    message_buffer = ''
    last_activity = time.time()
    in_signal = False
    receiving_message = False

    with sd.InputStream(callback=audio_callback, channels=1, samplerate=samplerate):
        print("Listening for sensor data...")
        while True:
            # Message completion check (2 seconds of silence)
            if receiving_message and (time.time() - last_activity) > 2:
                process_message(message_buffer)
                message_buffer = ''
                current_symbol = ''
                receiving_message = False
                print("\nReady for new transmission...")

            try:
                data = q.get_nowait().flatten()
                rms = np.sqrt(np.mean(np.square(data)))
                
                if rms > threshold and not in_signal:
                    in_signal = True
                    signal_start = time.time()
                    last_activity = signal_start
                    
                    # Detect message start
                    if not receiving_message:
                        receiving_message = True
                        message_buffer = ''
                        
                elif rms <= threshold and in_signal:
                    in_signal = False
                    signal_duration = time.time() - signal_start
                    last_activity = time.time()
                    
                    # Symbol detection
                    if signal_duration < 1.5*dot_duration:
                        current_symbol += '.'
                    else:
                        current_symbol += '-'
                        
                # Character/word space detection
                if not in_signal:
                    silence_duration = time.time() - last_activity
                    
                    # Word space (7+ dot durations)
                    if silence_duration > 7*dot_duration and message_buffer:
                        message_buffer += ' '
                        print(f"\rReceiving: {message_buffer}", end='', flush=True)
                    
                    # Character space (3+ dot durations)
                    elif silence_duration > 3*dot_duration and current_symbol:
                        char = MORSE_CODE_REVERSED.get(current_symbol, '')
                        message_buffer += char
                        current_symbol = ''
                        print(f"\rReceiving: {message_buffer}", end='', flush=True)

            except queue.Empty:
                time.sleep(0.01)

def process_message(raw_message):
    try:
        # Clean and validate message
        clean = raw_message.replace('...', '')  # Remove primer
        parts = [p.strip() for p in clean.split() if p.strip()]
        
        # Find the actual data payload between S and I
        try:
            start_idx = parts.index('S') + 1
            end_idx = parts.index('I')
            payload = parts[start_idx:end_idx]
        except ValueError:
            payload = parts[-7:]  # Fallback to last 7 elements
        
        if len(payload) != 7:
            print(f"\nInvalid format: {clean} (got {len(payload)}/7 values)")
            return

        print(f"\n\n=== Sensor Data @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
        print(f"Device:    {payload[0]}")
        print(f"CO:        {payload[1]} ppm")
        print(f"Temp:      {payload[2]} °C")
        print(f"PM1:       {payload[3]} µg/m³")
        print(f"PM2.5:     {payload[4]} µg/m³")
        print(f"PM4:       {payload[5]} µg/m³")
        print(f"PM10:      {payload[6]} µg/m³")
        print("========================================")

    except Exception as e:
        print(f"\nProcessing error: {str(e)}\nRaw: {raw_message}")

if __name__ == "__main__":
    listen_and_decode()