import serial
import time

# Serial Configuration
ser = serial.Serial('/dev/tty.usbserial-130', baudrate=9600, timeout=1)

# Morse Code Dictionary
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

# Morse Timing
DOT_DURATION = 0.2   # 200ms for a dot
DASH_DURATION = 0.6  # 600ms for a dash
SYMBOL_GAP = 0.2     # Gap between symbols
LETTER_GAP = 0.4     # Gap between letters
WORD_GAP = 0.8       # Gap between words

# Convert text to Morse Code
def text_to_morse(text):
    return ' '.join(MORSE_CODE_DICT[char] for char in text.upper() if char in MORSE_CODE_DICT)

# Function to send Morse Code as Digital Pulses
def send_message(text):
    print(f"Sending: {text}")
    morse_code = text_to_morse(text)

    for symbol in morse_code:
        if symbol == '.':
            ser.write(b'1')  # Send ON signal
            time.sleep(DOT_DURATION)
            ser.write(b'0')  # Send OFF signal
            time.sleep(SYMBOL_GAP)
        elif symbol == '-':
            ser.write(b'1')  # Send ON signal
            time.sleep(DASH_DURATION)
            ser.write(b'0')  # Send OFF signal
            time.sleep(SYMBOL_GAP)
        elif symbol == ' ':
            time.sleep(LETTER_GAP)  # Pause between letters
        elif symbol == '/':
            time.sleep(WORD_GAP)  # Pause between words

    print("Message sent.")

if __name__ == "__main__":
    send_message("SOS")  # Example transmission
