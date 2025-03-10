import serial
import time

# Serial Configuration
ser = serial.Serial('COM6', baudrate=9600, timeout=1)

# Morse Code Dictionary (Reverse Lookup)
MORSE_CODE_REVERSE = {v: k for k, v in {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.',
    'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---',
    'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---',
    'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
    'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--',
    'Z': '--..', '0': '-----', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..',
    '9': '----.', ' ': '/'
}.items()}

# Timing Thresholds
DOT_THRESHOLD = 0.3     # Below this = dot
DASH_THRESHOLD = 0.6    # Above dot but below this = dash
LETTER_GAP_THRESHOLD = 0.7
WORD_GAP_THRESHOLD = 1.2

def decode_morse(morse_code):
    words = morse_code.split(" / ")
    return ' '.join(''.join(MORSE_CODE_REVERSE.get(letter, '?') for letter in word.split()) for word in words)

# Function to receive Morse Code over COM
def receive_message():
    print("Listening for Morse code over COM...")
    morse_code = ""
    listening = False
    start_time = None
    last_signal_time = None

    while True:
        data = ser.read().decode().strip()

        if data == "1":  # Transmission started
            start_time = time.time()
            while ser.read().decode().strip() == "1":
                pass  # Wait for transmission to end
            duration = time.time() - start_time
            
            if duration < DOT_THRESHOLD:
                morse_code += "."
            elif duration < DASH_THRESHOLD:
                morse_code += "-"

        elif data == "0":  # Transmission stopped
            start_time = time.time()
            while ser.read().decode().strip() == "0":
                pass  # Wait for next transmission
            duration = time.time() - start_time

            if duration > WORD_GAP_THRESHOLD:
                morse_code += " / "
            elif duration > LETTER_GAP_THRESHOLD:
                morse_code += " "

        print(f"Current Morse Code: {morse_code}")

        # Stop listening when user interrupts
        if len(morse_code) > 50:  
            break

    decoded_message = decode_morse(morse_code)
    print(f"Final Decoded Message: {decoded_message}")

if __name__ == "__main__":
    receive_message()
