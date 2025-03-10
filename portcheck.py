import serial
import time

try:
    ser = serial.Serial("COM5", baudrate=9600, timeout=1)
    print("✅ Serial Port Opened")

    # Send a test byte
    ser.write(b"Test Morse Signal\n")
    time.sleep(1)

    ser.close()
    print("✅ Test signal sent!")
except serial.SerialException as e:
    print(f"❌ Error: {e}")
