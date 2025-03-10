import serial
import time

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

# Serial Port Configuration with improved baud rate
try:
    debug_log("Opening serial port at 9600 baud...")
    ser = serial.Serial('/dev/tty.usbserial-130', baudrate=9600, timeout=1)
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
    morse_code = ''
    for char in text.upper():
        if char in MORSE_CODE_DICT:
            morse_code += MORSE_CODE_DICT[char] + ' '
    debug_log(f"Morse Code: {morse_code.strip()}")
    return morse_code.strip()

# Function to send Morse Code message over serial with frequencies
def send_message(text):
    debug_log("Starting message transmission...")
    morse_code = text_to_morse(text)
    debug_log(f"Sending Morse Code: {morse_code}")

    for symbol in morse_code:
        if symbol == '.':
            debug_log("Sending DOT")
            send_signal(DOT_FREQUENCY, 0.2)  # Dot with duration
        elif symbol == '-':
            debug_log("Sending DASH")
            send_signal(DASH_FREQUENCY, 0.4)  # Dash with duration
        elif symbol == ' ':
            debug_log("Inter-letter space")
            time.sleep(0.3)  # Inter-letter space
        elif symbol == '/':
            debug_log("Inter-word space")
            time.sleep(0.7)  # Inter-word space
        
        # Only add symbol gap after dots and dashes
        if symbol in ['.', '-']:
            debug_log("Symbol gap")
            time.sleep(0.1)  # Gap between symbols

    debug_log("Message transmission complete.")

# Function to send a specific frequency signal with duration
def send_signal(frequency, duration):
    debug_log(f"Sending signal: Frequency={frequency}Hz, Duration={duration}s")
    
    # Send frequency data via serial
    ser.write(f"SIGNAL {frequency}\r\n".encode())
    ser.flush()
    
    # With 9600 baud, command transmission is practically instantaneous
    # Just wait for the specified duration
    time.sleep(duration)
    
    # Stop transmission
    debug_log("Sending STOP signal")
    ser.write(f"SIGNAL 0\r\n".encode())
    ser.flush()
    time.sleep(0.05)  # Brief pause to ensure the stop command is processed

# Function to send a single dot (for testing)
def send_single_dot():
    debug_log("Sending a single test dot...")
    send_signal(DOT_FREQUENCY, 0.2)
    debug_log("Single dot test complete.")

if __name__ == "__main__":
    try:
        debug_log("Program started.")
        
        # Uncomment one of these lines to test
        send_single_dot()   # For basic testing
        send_message("A") 
        # send_message("SOS") # For testing a short message
        
        debug_log("Program completed successfully.")
    finally:
        debug_log("Stopping any ongoing transmissions before closing...")
        ser.write(f"SIGNAL 0\r\n".encode())
        ser.flush()
        time.sleep(0.2)
        
        debug_log("Closing serial port...")
        ser.close()
        debug_log("Serial port closed.")