import numpy as np
import sounddevice as sd
import time
import datetime
import json
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
    '(': '-.--.', ')': '-.--.-', ' ': '/', '_': '..--.-'
}

frequency = 600
dot_duration = 0.1

def text_to_morse(text):
    return ' '.join(MORSE_CODE_DICT.get(i.upper(), '') for i in text)

def generate_tone(duration):
    t = np.linspace(0, duration, int(44100 * duration), False)
    return 0.5 * np.sin(2 * np.pi * frequency * t)

def play_morse(morse_code):
    primer = '... ... / '  # 6 dots for sync
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

def generate_device_data():
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "device_id": "device_1",
        "recorded_at": timestamp,
        "carbon_monoxide_ppm": round(random.uniform(0, 10.0), 1),
        "temperature_celcius": round(random.uniform(15, 30), 1),
        "pm1_ug_m3": round(random.uniform(0, 50), 1),
        "pm2_5_ug_m3": round(random.uniform(0, 100), 1),
        "pm4_ug_m3": round(random.uniform(0, 200), 1),
        "pm10_ug_m3": round(random.uniform(0, 300), 1)
    }

if __name__ == "__main__":
    while True:
        data = generate_device_data()
        # Convert to exact format string
        data_str = (
            f"{data['device_id']},"
            f"{data['recorded_at']},"
            f"{data['carbon_monoxide_ppm']},"
            f"{data['temperature_celcius']},"
            f"{data['pm1_ug_m3']},"
            f"{data['pm2_5_ug_m3']},"
            f"{data['pm4_ug_m3']},"
            f"{data['pm10_ug_m3']}"
        )
        print(f"Generated data: {data_str}")
        morse = text_to_morse(data_str)
        play_morse(morse)
        time.sleep(120)  # Send every minute