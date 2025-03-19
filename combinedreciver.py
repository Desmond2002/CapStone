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
    '--...': '7', '---..': '8', '----.': '9', '--..--': ',',
    '.-.-.-': '.', '-....-': '-', '-..-.': '/', '-..--': '|',
    '/': ' '
}

samplerate = 44100
threshold = 0.05  # More sensitive
dot_duration = 0.2  # Matches sender
q = queue.Queue()

def audio_callback(indata, frames, time, status):
    q.put(indata.copy())

def parse_data(payload):
    try:
        parts = payload.split('|')
        if len(parts) != 5: return None
        
        return {
            "device_id": parts[0],
            "timestamp": f"{parts[1][0:4]}-{parts[1][4:6]}-{parts[1][6:11]}:{parts[1][11:13]}:{parts[1][13:15]}",
            "carbon_monoxide_ppm": float(parts[2]),
            "temperature_celcius": float(parts[3]),
            "pm2_5_ug_m3": float(parts[4])
        }
    except Exception as e:
        print(f"Parse error: {e}")
        return None

def listen_and_decode():
    current_symbol = ''
    message_buffer = ''
    last_time = time.time()
    in_signal = False
    noise_buffer = 0.5  # Wait 500ms after signal ends

    with sd.InputStream(callback=audio_callback, channels=1, samplerate=samplerate):
        print("Listening for Morse code...")
        while True:
            try:
                data = q.get_nowait().flatten()
                rms = np.sqrt(np.mean(data**2))

                if rms > threshold and not in_signal:
                    in_signal = True
                    signal_start = time.time()
                    silence_duration = signal_start - last_time
                    
                    if silence_duration > (3*dot_duration + noise_buffer) and current_symbol:
                        char = MORSE_CODE_REVERSED.get(current_symbol, '?')
                        message_buffer += char
                        current_symbol = ''
                        print(f"\rReceived: {message_buffer}", end='', flush=True)

                elif rms <= threshold and in_signal:
                    in_signal = False
                    signal_duration = time.time() - signal_start
                    last_time = time.time()

                    if signal_duration < (1.5 * dot_duration):
                        current_symbol += '.'
                    else:
                        current_symbol += '-'

                # Finalize message after long silence
                if (time.time() - last_time) > (7 * dot_duration + noise_buffer):
                    if current_symbol:
                        char = MORSE_CODE_REVERSED.get(current_symbol, '?')
                        message_buffer += char
                        current_symbol = ''
                    
                    if message_buffer:
                        if '.../' in message_buffer and '/...' in message_buffer:
                            try:
                                payload = message_buffer.split('.../')[1].split('/...')[0].strip()
                                data = parse_data(payload)
                                if data:
                                    print("\n\nVALID TRANSMISSION:")
                                    print(json.dumps(data, indent=2))
                            except Exception as e:
                                print(f"\nDecoding error: {e}")
                        message_buffer = ''

            except queue.Empty:
                time.sleep(0.01)

if __name__ == "__main__":
    listen_and_decode()