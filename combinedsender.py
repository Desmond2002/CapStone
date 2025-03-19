import numpy as np
import sounddevice as sd
import time
import datetime
import json
import os
import random

MORSE_CODE_DICT = { 
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.',
    'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---',
    'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---',
    'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
    'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--',
    'Z': '--..', '0': '-----', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..',
    '9': '----.', ',': '--..--', '.': '.-.-.-', '-': '-....-', '/': '-..-.',
    '|': '-..--'  # Custom separator
}

SAFE_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-,.|/'  # Limited character set
frequency = 600  # Hz
dot_duration = 0.2  # Slower transmission speed

def text_to_morse(text):
    cleaned = ''.join([c for c in text.upper() if c in SAFE_CHARS])
    return ' '.join(MORSE_CODE_DICT.get(c, '') for c in cleaned)

def generate_tone(duration):
    t = np.linspace(0, duration, int(44100 * duration), False)
    return 0.5 * np.sin(2 * np.pi * frequency * t)

def play_morse(morse_code):
    primer = '... / '
    morse_code = primer + morse_code + ' /'
    
    for symbol in morse_code:
        if symbol == '.':
            sd.play(generate_tone(dot_duration), samplerate=44100)
            sd.wait()
            time.sleep(dot_duration * 1.2)  # Extended spacing
        elif symbol == '-':
            sd.play(generate_tone(3*dot_duration), samplerate=44100)
            sd.wait()
            time.sleep(dot_duration * 1.2)
        elif symbol == ' ':
            time.sleep(3 * dot_duration)
        elif symbol == '/':
            time.sleep(7 * dot_duration)

# Data generation functions
PREVIOUS_READINGS_FILE = "previous_readings.json"

def load_previous_readings():
    if os.path.exists(PREVIOUS_READINGS_FILE):
        with open(PREVIOUS_READINGS_FILE, 'r') as f:
            try: return json.load(f)
            except: pass
    return {"device_1": {"co": 0, "temperature": 20, "pm1": 0, "pm2_5": 0}}

def save_previous_readings(data):
    with open(PREVIOUS_READINGS_FILE, 'w') as f:
        json.dump(data, f)

def generate_reading(device_id, previous):
    prev = previous.get(device_id, {"co": 0, "temperature": 20})
    new_co = max(0, prev["co"] + random.uniform(-0.5, 1.0))
    new_temp = prev["temperature"] + random.uniform(-0.5, 0.5)
    new_pm = max(0, prev["pm2_5"] + random.uniform(-2.0, 5.0))
    
    previous[device_id] = {
        "co": round(new_co, 1),
        "temperature": round(new_temp, 1),
        "pm2_5": round(new_pm, 1)
    }
    
    return {
        "device_id": device_id,
        "timestamp": datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S"),
        "co_ppm": previous[device_id]["co"],
        "temp_c": previous[device_id]["temperature"],
        "pm2_5": previous[device_id]["pm2_5"]
    }

if __name__ == "__main__":
    device_id = "DEV1"
    previous = load_previous_readings()
    
    try:
        while True:
            reading = generate_reading(device_id, previous)
            data_str = (f"{reading['device_id']}|"
                        f"{reading['timestamp']}|"
                        f"{reading['co_ppm']:.1f}|"
                        f"{reading['temp_c']:.1f}|"
                        f"{reading['pm2_5']:.1f}")
            
            print(f"Original: {data_str}")
            morse = text_to_morse(data_str)
            play_morse(morse)
            save_previous_readings(previous)
            time.sleep(180)
            
    except KeyboardInterrupt:
        save_previous_readings(previous)
        print("\nTransmission stopped.")