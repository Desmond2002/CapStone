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

# Serial Port Configuration (For Mac: /dev/tty.usbserial-130)
try:
    debug_log("Opening serial port at 110 baud...")
    ser = serial.Serial('/dev/tty.usbserial-130', baudrate=110, timeout=1)
    debug_log("Serial port opened successfully.")
except serial.SerialException:
    print("Error: Could not open serial port.")
    exit()

# Signal Timing Definitions (in milliseconds)
DOT_DURATION = 100  # 1 unit
DASH_DURATION = DOT_DURATION * 3  # 3 units
INTRA_SYMBOL_GAP = DOT_DURATION  # 1 unit (between dots and dashes in the same letter)
LETTER_GAP = DOT_DURATION * 3  # 3 units (between letters)
WORD_GAP = DOT_DURATION * 7  # 7 units (between words)

# Frequencies for signals (in Hz)
DOT_FREQUENCY = 800  # Frequency for dots
DASH_FREQUENCY = 600  # Frequency for dashes

# Convert text to Morse Code
def text_to_morse(text):
    debug_log(f"Converting text to Morse Code: {text}")
    morse_code = ' '.join(MORSE_CODE_DICT[char] for char in text.upper() if char in MORSE_CODE_DICT)
    debug_log(f"Morse Code: {morse_code}")
    return morse_code

# Function to send Morse Code message over serial with defined durations & frequencies
def send_message(text):
    debug_log("Starting message transmission...")
    morse_code = text_to_morse(text)

    # Process each character in Morse code
    for i, char in enumerate(morse_code):
        if char == '.':
            send_signal(DOT_FREQUENCY, DOT_DURATION)  # Dot
        elif char == '-':
            send_signal(DASH_FREQUENCY, DASH_DURATION)  # Dash
        elif char == ' ':
            time.sleep(LETTER_GAP / 1000.0)  # Inter-letter space
        elif char == '/':
            time.sleep(WORD_GAP / 1000.0)  # Inter-word space
        
        # Intra-symbol gap (between dots and dashes in the same letter)
        if i < len(morse_code) - 1 and morse_code[i+1] not in [' ', '/']:
            time.sleep(INTRA_SYMBOL_GAP / 1000.0)

    debug_log("Message transmission complete.")

# Function to simulate sending a signal with a specific frequency and duration
def send_signal(frequency, duration):
    debug_log(f"Sending signal: Frequency={frequency}Hz, Duration={duration}ms")
    
    # Simulate sending signal (replace with actual transmission logic)
    ser.write(f"SIGNAL {frequency} {duration}\n".encode())  # Example format
    ser.flush()
    
    time.sleep(duration / 1000.0)  # Hold signal for duration

if __name__ == "__main__":
    try:
        debug_log("Program started.")
        send_message("HELLO")  # Test message
        debug_log("Program completed successfully.")
    finally:
        debug_log("Closing serial port...")
        ser.close()
        debug_log("Serial port closed.")
