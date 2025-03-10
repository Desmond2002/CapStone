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
#for mac com port is /dev/tty.usbserial-130
# Open serial port at 110 baud
try:
    debug_log("Opening serial port COM5 at 110 baud...")
    ser = serial.Serial('/dev/tty.usbserial-130', baudrate=110, timeout=1)
    debug_log("Serial port opened successfully.")
except serial.SerialException:
    print("Error: Could not open serial port.")
    exit()

# Convert text to Morse Code
def text_to_morse(text):
    debug_log(f"Converting text to Morse Code: {text}")
    morse_code = ' '.join(MORSE_CODE_DICT[char] for char in text.upper() if char in MORSE_CODE_DICT)
    debug_log(f"Morse Code: {morse_code}")
    return morse_code

# Function to send Morse Code message over serial (with adjusted durations)
def send_message(text):
    debug_log("Starting message transmission...")
    morse_code = text_to_morse(text)
    
    binary_morse = ""

    # Process each character in Morse code
    for i, char in enumerate(morse_code):
        if char == '.':
            binary_morse += '111'  # Dot is now 3 units long
            if i < len(morse_code) - 1 and morse_code[i+1] not in [' ', '/']:
                binary_morse += '00'  # Space between symbols in the same letter
        elif char == '-':
            binary_morse += '111111111'  # Dash is now 9 units long
            if i < len(morse_code) - 1 and morse_code[i+1] not in [' ', '/']:
                binary_morse += '00'  # Space between symbols in the same letter
        elif char == ' ':
            binary_morse += '000'  # Space between letters
        elif char == '/':
            binary_morse += '000000'  # Space between words
    
    debug_log(f"Sending Morse Code as binary: {binary_morse}")

    # Convert to bytes and send over serial
    ser.write(binary_morse.encode())  # Encode string to bytes
    ser.flush()

    debug_log("Message transmission complete.")

if __name__ == "__main__":
    try:
        debug_log("Program started.")
        send_message("A")  # Test with "A"
        debug_log("Program completed successfully.")
    finally:
        debug_log("Closing serial port...")
        ser.close()
        debug_log("Serial port closed.")
