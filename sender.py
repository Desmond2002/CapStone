import json
import datetime
import os
import random
import time
import numpy as np
import sounddevice as sd

PROGRESS_FILE = "progress.json"
PREVIOUS_READINGS_FILE = "previous_readings.json"
device_ids = ["device_1"]

# Radio transmission configuration
MORSE_CODE_DICT = {
    # Optimized numbers (shorter codes)
    '0': '-',    # Was '-----' (5)
    '1': '.-',   # Was '.----' (5)
    '2': '..-',  # Was '..---' (5)
    '3': '...-', # Was '...--' (5)
    '4': '....',
    '5': '.....',
    '6': '-....',
    '7': '-...',
    '8': '-..',
    '9': '-.',
    # Special characters
    '.': '.-.-',  # Decimal point
    ' ': '/',      # Space
    '_': '..--'    # Device ID separator
}

FREQUENCY = 600
dot_duration = 0.1

def text_to_morse(text):
    return ' '.join(MORSE_CODE_DICT.get(i, '') for i in text)

def generate_tone(duration):
    t = np.linspace(0, duration, int(44100 * duration), False)
    return 0.5 * np.sin(2 * np.pi * FREQUENCY * t)

def play_morse(morse_code):
    primer = '... / '
    morse_code = primer + morse_code + ' /'
    
    for symbol in morse_code:
        if symbol == '.':
            sd.play(generate_tone(dot_duration), samplerate=44100)
            sd.wait()
            time.sleep(dot_duration)  # Inter-symbol space
        elif symbol == '-':
            sd.play(generate_tone(3*dot_duration), samplerate=44100)
            sd.wait()
            time.sleep(dot_duration)  # Inter-symbol space
        elif symbol == ' ':
            time.sleep(3*dot_duration)  # Inter-character space
        elif symbol == '/':
            time.sleep(7*dot_duration)  # Inter-word space


def load_previous_readings():
    if os.path.exists(PREVIOUS_READINGS_FILE):
        with open(PREVIOUS_READINGS_FILE, 'r') as file:
            try:
                return json.load(file)
            except (json.JSONDecodeError, TypeError):
                pass
    return {device_id: {"co": 0, "temperature": 20, "pm1": 0, "pm2_5": 0, "pm4": 0, "pm10": 0} for device_id in device_ids}

def save_previous_readings(previous_readings):
    with open(PREVIOUS_READINGS_FILE, 'w') as file:
        json.dump(previous_readings, file)

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as file:
            try:
                data = json.load(file)
                return data.get("last_timestamp") if isinstance(data, dict) and "last_timestamp" in data else None
            except json.JSONDecodeError:
                return None
    return None

def save_progress(timestamp):
    with open(PROGRESS_FILE, 'w') as file:
        json.dump({"last_timestamp": timestamp}, file)

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

    previous_readings[device_id] = {
        "co": co_level,
        "temperature": temperature,
        "pm1": pm1,
        "pm2_5": pm2_5,
        "pm4": pm4,
        "pm10": pm10
    }

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

def handle_reading(timestamp, device_id, previous_readings):
    reading = generate_reading(device_id, previous_readings, timestamp)
    
    # Create transmission message (device number + sensor values)
    values = [
        reading['device_id'].split('_')[1],  # Device number
        f"{reading['carbon_monoxide_ppm']:.2f}",
        f"{reading['temperature_celcius']:.2f}",
        f"{reading['pm1_ug_m3']:.2f}",
        f"{reading['pm2_5_ug_m3']:.2f}",
        f"{reading['pm4_ug_m3']:.2f}",
        f"{reading['pm10_ug_m3']:.2f}"
    ]
    message = ' '.join(values)
    
    print(f"Transmitting: {message}")
    play_morse(text_to_morse(message))

def main():
    last_timestamp = load_progress()
    previous_readings = load_previous_readings()

    # Calculate next transmission time
    if last_timestamp:
        next_transmission = datetime.datetime.fromisoformat(last_timestamp).astimezone(datetime.timezone.utc)
    else:
        next_transmission = datetime.datetime.now(datetime.timezone.utc)

    try:
        while True:
            # Calculate sleep duration
            now = datetime.datetime.now(datetime.timezone.utc)
            sleep_seconds = (next_transmission - now).total_seconds()
            
            if sleep_seconds > 0:
                print(f"Next transmission at {next_transmission.isoformat()}")
                time.sleep(sleep_seconds)

            # Generate and transmit reading
            transmission_time = datetime.datetime.now(datetime.timezone.utc)
            for device_id in device_ids:
                handle_reading(transmission_time, device_id, previous_readings)

            # Update and save progress
            next_transmission = transmission_time + datetime.timedelta(minutes=3)
            save_progress(transmission_time.isoformat())
            save_previous_readings(previous_readings)

    except KeyboardInterrupt:
        print("\nInterrupted. Saving progress before exiting...")
        save_progress(next_transmission.isoformat())
        save_previous_readings(previous_readings)
        print("Progress saved. You can resume later.")

if __name__ == "__main__":
    main()