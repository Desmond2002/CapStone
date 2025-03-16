import numpy as np
import serial
import time

# OFDM Parameters
N_CARRIERS = 64   # Number of subcarriers
CP_LEN = 16       # Cyclic prefix length
FS = 44100        # Sampling rate
FREQ_SPACING = 1000  # Subcarrier spacing in Hz

# Configure Serial Port
SERIAL_PORT = "COM5"  # Change to your COM port
BAUD_RATE = 9600
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

def text_to_bits(text):
    """ Convert text to binary representation """
    return ''.join(format(ord(i), '08b') for i in text)

def generate_cofdm_symbols(data_bits):
    """ Encode binary data into COFDM symbols """
    bit_groups = [data_bits[i:i+N_CARRIERS] for i in range(0, len(data_bits), N_CARRIERS)]
    symbols = []

    for group in bit_groups:
        symbol = np.array([1 if bit == '1' else -1 for bit in group.ljust(N_CARRIERS, '0')])
        symbols.append(symbol)
    
    return np.array(symbols)

def cofdm_modulate(symbols):
    """ Perform IFFT on symbols to generate COFDM signal """
    time_domain_signals = []
    
    for symbol in symbols:
        freq_domain_signal = np.fft.ifft(symbol)  # Inverse FFT
        cyclic_prefix = freq_domain_signal[-CP_LEN:]  # Add cyclic prefix
        time_domain_signal = np.concatenate((cyclic_prefix, freq_domain_signal))
        time_domain_signals.append(time_domain_signal)
    
    return np.concatenate(time_domain_signals).real  # Ensure real values for transmission

def send_data_via_serial(data):
    """ Send COFDM modulated signal via serial """
    for value in data:
        ser.write(f"{value}\n".encode())
        time.sleep(0.001)  # Small delay to avoid buffer overflow

if __name__ == "__main__":
    text = "Hello, COFDM!"
    bits = text_to_bits(text)
    cofdm_symbols = generate_cofdm_symbols(bits)
    cofdm_signal = cofdm_modulate(cofdm_symbols)

    print("Sending data...")
    send_data_via_serial(cofdm_signal)
    
    ser.close()
    print("Transmission complete!")