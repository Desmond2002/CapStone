import serial
import time
import numpy as np

# Debugging function
def debug_log(message):
    print(f"[DEBUG] {message}")

# Morse Code dictionary
MORSE_CODE_DICT = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.',
    'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---',
    'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---',
    'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
    'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--',
    'Z': '--..', '0': '-----', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..',
    '9': '----.', ' ': '/'
}

# Serial Port Configuration (For Mac: /dev/tty.usbserial-130)
try:
    debug_log("Opening serial port at 110 baud...")
    ser = serial.Serial('/dev/tty.usbserial-130', baudrate=110, timeout=1)
    debug_log("Serial port opened successfully.")
except serial.SerialException:
    print("Error: Could not open serial port.")
    exit()

# Frequencies for signals (in Hz)
DOT_FREQUENCY = 800  # Frequency for dots
DASH_FREQUENCY = 600  # Frequency for dashes

# Convert text to Morse Code
def text_to_morse(text):
    debug_log(f"Converting text to Morse Code: {text}")
    morse_code = ' '.join(MORSE_CODE_DICT[char] for char in text.upper() if char in MORSE_CODE_DICT)
    debug_log(f"Morse Code: {morse_code}")
    return morse_code

# Function to send Morse Code message over serial with frequencies
def send_message(text):
    debug_log("Starting message transmission...")
    morse_code = text_to_morse(text)

    for char in morse_code:
        if char == '.':
            send_signal(DOT_FREQUENCY)  # Dot
        elif char == '-':
            send_signal(DASH_FREQUENCY)  # Dash
        elif char == ' ':
            time.sleep(0.3)  # Inter-letter space
        elif char == '/':
            time.sleep(0.7)  # Inter-word space
        time.sleep(0.1)  # Intra-symbol gap

    debug_log("Message transmission complete.")

# Function to send a specific frequency signal
def send_signal(frequency):
    debug_log(f"Sending signal: Frequency={frequency}Hz")

    # Send frequency data via serial
    ser.write(f"SIGNAL {frequency}\n".encode())  
    ser.flush()
    
    time.sleep(0.1)  # Hold signal for 100ms

if __name__ == "__main__":
    try:
        debug_log("Program started.")
        send_message("A")  # Send Morse code for "A"
        debug_log("Program completed successfully.")
    finally:
        debug_log("Closing serial port...")
        ser.close()
        debug_log("Serial port closed.")
