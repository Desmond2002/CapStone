import json
import datetime
import os
import random
import time

PROGRESS_FILE = "progress.json"
PREVIOUS_READINGS_FILE = "previous_readings.json"

device_ids = ["device_1"]

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
    """Load the last timestamp from the progress file."""
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

    previous_readings[device_id] = {"co": co_level, "temperature": temperature, "pm1": pm1, "pm2_5": pm2_5, "pm4": pm4, "pm10": pm10}

    return {
        "device_id": str(device_id),
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
    print(f"Generated reading: {json.dumps(reading, indent=2)}")

def main(start_date, end_date):
    last_timestamp = load_progress()
    previous_readings = load_previous_readings()

    start_dt = datetime.datetime.fromisoformat(start_date).replace(tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime.fromisoformat(end_date).replace(tzinfo=datetime.timezone.utc)

    if last_timestamp:
        start_dt = datetime.datetime.fromisoformat(last_timestamp).replace(tzinfo=datetime.timezone.utc)

    current_dt = start_dt

    try:
        while current_dt < end_dt:
            for device_id in device_ids:
                handle_reading(current_dt, device_id, previous_readings)

            save_progress(current_dt.isoformat())
            save_previous_readings(previous_readings)

            # Add the 3-minute delay here
            time.sleep(180)  # 180 seconds = 3 minutes
            
            current_dt += datetime.timedelta(minutes=3)
            
    except KeyboardInterrupt:
        print("\nInterrupted. Saving progress before exiting...")
        save_progress(current_dt.isoformat())
        save_previous_readings(previous_readings)
        print("Progress saved. You can resume later.")

if __name__ == "__main__":
    main("2024-07-19T03:15:00", "2025-01-31T00:00:00")