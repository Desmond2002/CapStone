import numpy as np
import sounddevice as sd
import time
from datetime import datetime, timedelta
import random
import json
import os

# Configuration - Adjust these values
TRANSMISSION_INTERVAL = 1  # Minutes between transmissions
DEVICE_ID = "01"           # Device identifier

MORSE_CODE = {
    '0': '-', '1': '.', '2': '.-', '3': '..-', '4': '...-',
    '5': '....-', '6': '-....', '7': '-.-', '8': '--.', 
    '9': '---', '#': '-...-'
}

# Transmission timing (seconds)
dot_duration = 0.15
dash_duration = 0.3
inter_symbol_pause = dot_duration
inter_char_pause = 2 * dot_duration

# Derived configuration
transmission_interval = TRANSMISSION_INTERVAL * 60  # Convert to seconds

PREVIOUS_READINGS_FILE = "sender_previous_readings.json"

def load_previous_readings():
    if os.path.exists(PREVIOUS_READINGS_FILE):
        try:
            with open(PREVIOUS_READINGS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"co": 0, "temperature": 20, "pm1": 0, "pm2_5": 0, "pm4": 0, "pm10": 0}

def save_previous_readings(prev):
    with open(PREVIOUS_READINGS_FILE, 'w') as f:
        json.dump(prev, f)

def generate_sensor_data(prev):
    new_data = {
        "co": max(0, min(prev["co"] + random.uniform(-0.5, 1.0), 99)),
        "temperature": max(-40, min(prev["temperature"] + random.uniform(-0.5, 0.5), 85)),
        "pm1": max(0, prev["pm1"] + random.uniform(-0.5, 1.5)),
        "pm2_5": max(0, prev["pm2_5"] + random.uniform(-0.5, 1.5)),
        "pm4": max(0, prev["pm4"] + random.uniform(-5, 5)),
        "pm10": max(0, prev["pm10"] + random.uniform(-0.5, 2.0))
    }
    return {k: round(v, 1) for k, v in new_data.items()}

def scale_sensor_data(sensor_values):
    return {
        "co": f"{int(round(sensor_values['co'])):02d}",
        "temp": f"{int(round(sensor_values['temperature'])):02d}",
        "pm1": f"{int(round(sensor_values['pm1'])):02d}",
        "pm2_5": f"{int(round(sensor_values['pm2_5'] * 10)):03d}",
        "pm4": f"{int(round(sensor_values['pm4'])):03d}",
        "pm10": f"{int(round(sensor_values['pm10'])):02d}"
    }

def generate_tone(duration):
    t = np.linspace(0, duration, int(44100 * duration), False)
    return 0.5 * np.sin(2 * np.pi * 800 * t)  # 800Hz frequency

def play_morse(code):
    for symbol in code:
        if symbol == '.':
            sd.play(generate_tone(dot_duration), samplerate=44100)
            sd.wait()
            time.sleep(inter_symbol_pause)
        elif symbol == '-':
            sd.play(generate_tone(dash_duration), samplerate=44100)
            sd.wait()
            time.sleep(inter_symbol_pause)

if __name__ == "__main__":
    prev_readings = load_previous_readings()
    
    while True:
        sensor_data = generate_sensor_data(prev_readings)
        scaled = scale_sensor_data(sensor_data)
        save_previous_readings(sensor_data)
        
        now = datetime.now()
        midnight = now.replace(hour=0, minute=0, second=0)
        packet_num = (now - midnight).seconds // (TRANSMISSION_INTERVAL * 60)
        
        data_str = (
            DEVICE_ID +
            f"{packet_num:04d}" +
            scaled["co"] +
            scaled["temp"] +
            scaled["pm1"] +
            scaled["pm2_5"] +
            scaled["pm4"] +
            scaled["pm10"]
        )
        
        checksum = sum(int(c) for c in data_str) % 10
        full_msg = f"#{data_str}{checksum}#"
        
        print(f"\nEncoded: {full_msg}")
        print("Morse:", " ".join([MORSE_CODE[c] for c in full_msg]))
        
        start_time = time.time()
        for c in full_msg:
            code = MORSE_CODE.get(c, '')
            if code:
                play_morse(code)
                time.sleep(inter_char_pause)
        
        tx_time = time.time() - start_time
        print(f"Transmitted in {tx_time:.2f}s")
        time.sleep(max(0, transmission_interval - tx_time))