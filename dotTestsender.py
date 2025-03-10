import serial
import time

# Debug function
def debug_log(message):
    print(f"[DEBUG] {message}")

# Serial Port Configuration
PORT = "/dev/tty.usbserial-130"  # Change for Windows (e.g., "COM5")
BAUDRATE = 110
DOT_DURATION = 0.2  # Adjust for timing consistency (200ms dot)
GAP_DURATION = 0.2  # Gap between dots

# Open Serial Port
try:
    debug_log(f"Opening serial port {PORT} at {BAUDRATE} baud...")
    ser = serial.Serial(PORT, baudrate=BAUDRATE, timeout=1)
    debug_log("Serial port opened successfully.")
except serial.SerialException:
    print("Error: Could not open serial port.")
    exit()

def send_dot():
    """Sends a single dot signal over the serial connection."""
    debug_log("Sending dot signal...")
    
    ser.write(b'1')  # Send binary '1' as a dot
    ser.flush()
    time.sleep(DOT_DURATION)  # Duration of dot
    
    ser.write(b'0')  # Send binary '0' to indicate silence
    ser.flush()
    time.sleep(GAP_DURATION)  # Wait before sending the next dot

if __name__ == "__main__":
    try:
        debug_log("Starting continuous dot transmission...")
        while True:
            send_dot()  # Send dots continuously
    except KeyboardInterrupt:
        debug_log("Stopping transmission.")
    finally:
        debug_log("Closing serial port...")
        ser.close()
        debug_log("Serial port closed.")
