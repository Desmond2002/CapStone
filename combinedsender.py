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
    'Z': '--..', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....', '7': '--...',
    '8': '---..', '9': '----.', '0': '-----', ',': '--..--',
    '.': '.-.-.-', '?': '..--..', '/': '-..-.', '-': '-....-',
    '(': '-.--.', ')': '-.--.-', ' ': '/'
}

frequency = 600  # Hz
dot_duration = 0.1  # Seconds

def text_to_morse(text):
    return ' '.join(MORSE_CODE_DICT.get(i.upper(), '') for i in text)

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
            time.sleep(dot_duration)
        elif symbol == '-':
            sd.play(generate_tone(3*dot_duration), samplerate=44100)
            sd.wait()
            time.sleep(dot_duration)
        elif symbol == ' ':
            time.sleep(3*dot_duration)
        elif symbol == '/':
            time.sleep(7*dot_duration)

PREVIOUS_READINGS_FILE = "previous_readings.json"

def load_previous_readings():
    if os.path.exists(PREVIOUS_READINGS_FILE):
        with open(PREVIOUS_READINGS_FILE, 'r') as file:
            try:
                return json.load(file)
            except (json.JSONDecodeError, TypeError):
                pass
    return {"device_1": {"co": 0, "temperature": 20, "pm1": 0, "pm2_5": 0, "pm4": 0, "pm10": 0}}

def save_previous_readings(previous_readings):
    with open(PREVIOUS_READINGS_FILE, 'w') as file:
        json.dump(previous_readings, file)

def generate_reading(device_id, previous_readings, timestamp):
    prev = previous_readings.get(device_id, {"co": 0, "temperature": 20, "pm1": 0, "pm2_5": 0, "pm4": 0, "pm10": 0})

    if prev["co"] < 6.0:
        co_level = max(0, round(prev["co"] + random.uniform(-0.05, 1.0), 2))
    else:
        co_level = max(0, round(prev["co"] + random.uniform(-1.5, 0.25), 2))

    if prev["temperature"] < 10.0:
        temperature = round(prev["temperature"] + random.uniform(0, 0.25), 2)
    elif prev["temperature"] > 30:
        temperature = round(prev["temperature"] + random.uniform(-1.0, 0.25), 2)
    else:
        temperature = round(prev["temperature"] + random.uniform(-0.25, 0.25), 2)

    if prev["pm1"] < 42.4:
        pm1 = max(0, round(prev["pm1"] + random.uniform(-0.1, 0.3), 2))
    else:
        pm1 = max(0, round(prev["pm1"] + random.uniform(-0.4, 0.4), 2))

    if prev["pm2_5"] < 22.0:
        pm2_5 = max(0, round(prev["pm2_5"] + random.uniform(-0.15, 0.15), 2))
    else:
        pm2_5 = max(0, round(prev["pm2_5"] + random.uniform(-0.15, 0.16), 2))

    if prev["pm4"] < 492.0:
        pm4 = max(0, round(prev["pm4"] + random.uniform(-0.3, 0.8), 2))
    else:
        pm4 = max(0, round(prev["pm4"] + random.uniform(-7.5, 7.5), 2))

    if prev["pm10"] < 5.5:
        pm10 = max(0, round(prev["pm10"] + random.uniform(-0.4, 0.9), 2))
    else:
        pm10 = max(0, round(prev["pm10"] + random.uniform(-0.15, 0.15), 2))

    previous_readings[device_id] = {"co": co_level, "temperature": temperature, "pm1": pm1, "pm2_5": pm2_5, "pm4": pm4, "pm10": pm10}

    return {
        "device_id": device_id,
        "recorded_at": timestamp.replace(microsecond=0).isoformat(),
        "carbon_monoxide_ppm": float(co_level),
        "temperature_celcius": float(temperature),
        "pm1_ug_m3": float(pm1),
        "pm2_5_ug_m3": float(pm2_5),
        "pm4_ug_m3": float(pm4),
        "pm10_ug_m3": float(pm10)
    }

if __name__ == "__main__":
    device_id = "device_1"
    previous_readings = load_previous_readings()

    try:
        while True:
            current_dt = datetime.datetime.now(datetime.timezone.utc)
            reading = generate_reading(device_id, previous_readings, current_dt)
            formatted_timestamp = reading['recorded_at'].replace(':', '-')
            data_str = (
                f"{reading['device_id']},"
                f"{formatted_timestamp},"
                f"{reading['carbon_monoxide_ppm']},"
                f"{reading['temperature_celcius']},"
                f"{reading['pm1_ug_m3']},"
                f"{reading['pm2_5_ug_m3']},"
                f"{reading['pm4_ug_m3']},"
                f"{reading['pm10_ug_m3']}"
            )
            morse = text_to_morse(data_str)
            print(f"Sending: {morse}")
            play_morse(morse)
            save_previous_readings(previous_readings)
            time.sleep(180)
    except KeyboardInterrupt:
        save_previous_readings(previous_readings)
        print("\nSender stopped. Previous readings saved.")