import serial
import time

# Serial Port Configuration
PORT = "/dev/tty.usbserial-130"  # Change for Windows (e.g., "COM5")
BAUDRATE = 110

# Open Serial Port
try:
    print(f"Opening serial port {PORT} at {BAUDRATE} baud...")
    ser = serial.Serial(PORT, baudrate=BAUDRATE, timeout=1)
    print("Serial port opened successfully.")
except serial.SerialException:
    print("Error: Could not open serial port.")
    exit()

last_dot_time = None  # Stores when the dot started
dot_durations = []  # Stores all detected dot durations for analysis

def log_dot_duration(start, end):
    """Logs the duration of a detected dot and checks for interference."""
    duration = (end - start) * 1000  # Convert to milliseconds
    dot_durations.append(duration)

    # Check for interference if the dot duration deviates significantly
    if abs(duration - 150) > 15:  # Tolerance range ±15ms
        print(f"[INTERFERENCE?] Dot Duration: {duration:.1f}ms (Expected: 150ms)")

    else:
        print(f"[DOT DETECTED] Duration: {duration:.1f}ms")

if __name__ == "__main__":
    print("Listening for Morse dots... Press Ctrl+C to stop.")
    try:
        while True:
            data = ser.read()  # Read one byte at a time
            if data == b'1':  # Start of dot
                last_dot_time = time.time()
                print("[START] Dot detected...")
            
            elif data == b'0' and last_dot_time is not None:  # End of dot
                end_time = time.time()
                log_dot_duration(last_dot_time, end_time)
                last_dot_time = None  # Reset for next dot

    except KeyboardInterrupt:
        print("\nStopping receiver...")

        # Display final timing analysis
        if dot_durations:
            avg_duration = sum(dot_durations) / len(dot_durations)
            print(f"\n[FINAL ANALYSIS] Average Dot Duration: {avg_duration:.1f}ms")
            print(f"[DOT COUNT] {len(dot_durations)} dots detected")

        ser.close()
        print("Serial port closed.")
