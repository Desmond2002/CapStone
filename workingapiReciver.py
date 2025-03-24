import numpy as np
import sounddevice as sd
import queue
import time
from datetime import datetime, timedelta
import requests

# Configuration - Must match sender!
TRANSMISSION_INTERVAL = 1  # Minutes between transmissions

REVERSE_MORSE = {
    '-': '0', '.': '1', '.-': '2', '..-': '3',
    '...-': '4', '....-': '5', '-....': '6',
    '-.-': '7', '--.': '8', '---': '9',
    '-...-': '#'
}

# Receiver timing (match sender's dot duration)
dot_duration = 0.15
dash_threshold = 0.27  # 1.8 * dot_duration
inter_char_pause = 0.3  # 2 * dot_duration
threshold = 0.05
debounce_count = 2

POST_TO_API = False
API_URL = "https://findthefrontier.ca/spark/data"

q = queue.Queue()

def audio_callback(indata, frames, time, status):
    q.put(indata.copy())

def listen():
    buffer = []
    current_symbol = ''
    last_signal_end = time.time()
    in_signal = False
    signal_samples = 0
    recording = False

    print("Initializing audio...")
    with sd.InputStream(callback=audio_callback, samplerate=44100) as stream:
        print(f"Using {stream.device} at {stream.samplerate}Hz")
        print("Listening... (Ctrl+C to stop)")
        
        while True:
            try:
                data = q.get_nowait().flatten()
                rms = np.sqrt(np.mean(data**2))
                now = time.time()
                
                if rms > threshold:
                    signal_samples += 1
                    if not in_signal and signal_samples >= debounce_count:
                        in_signal = True
                        signal_start = now
                        print(".", end="", flush=True)
                else:
                    signal_samples = 0
                    if in_signal:
                        in_signal = False
                        duration = now - signal_start
                        last_signal_end = now
                        current_symbol += '.' if duration < dash_threshold else '-'
                
                if not in_signal and (now - last_signal_end) > inter_char_pause:
                    if current_symbol:
                        char = REVERSE_MORSE.get(current_symbol, '?')
                        print(f" → {char}", flush=True)
                        
                        if char == '#':
                            if not recording:
                                print("\n--- START ---")
                                recording = True
                                buffer = []
                            else:
                                print("\n--- END ---")
                                recording = False
                                process_message(''.join(buffer))
                                buffer = []
                        elif recording:
                            buffer.append(char)
                        
                        current_symbol = ''
                
            except queue.Empty:
                time.sleep(0.01)
            except KeyboardInterrupt:
                return

def process_message(msg):
    try:
        if len(msg) != 21:
            print(f"Invalid length {len(msg)} (expected 21)")
            return
        
        payload = {
            "device_id": msg[0:2],
            "packet_num": int(msg[2:6]),
            "carbon_monoxide_ppm": int(msg[6:8]),
            "temperature_celcius": int(msg[8:10]),
            "pm1_ug_m3": int(msg[10:12]),
            "pm2_5_ug_m3": int(msg[12:15])/10.0,
            "pm4_ug_m3": int(msg[15:18]),
            "pm10_ug_m3": int(msg[18:20])
        }
        
        if sum(int(c) for c in msg[:20]) %10 != int(msg[20]):
            print("Checksum mismatch")
            return
        
        midnight = datetime.now().replace(hour=0, minute=0, second=0)
        timestamp = midnight + timedelta(minutes=payload['packet_num']*TRANSMISSION_INTERVAL)
        
        print(f"\nValid Packet @ {timestamp.strftime('%Y-%m-%d %H:%M')}:")
        print(f"CO: {payload['carbon_monoxide_ppm']} ppm")
        print(f"Temp: {payload['temperature_celcius']}°C")
        print(f"PM1: {payload['pm1_ug_m3']} µg/m³")
        print(f"PM2.5: {payload['pm2_5_ug_m3']:.1f} µg/m³")
        print(f"PM4: {payload['pm4_ug_m3']} µg/m³")
        print(f"PM10: {payload['pm10_ug_m3']} µg/m³")
        
        if POST_TO_API:
            payload["recorded_at"] = timestamp.isoformat()
            response = requests.post(API_URL, json=payload)
            print(f"API Status: {response.status_code}")
            
    except Exception as e:
        print(f"Processing error: {str(e)}")

if __name__ == "__main__":
    listen()
