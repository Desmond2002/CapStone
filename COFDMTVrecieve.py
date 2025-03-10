import numpy as np
import pyaudio
import struct
import time

# OFDM Parameters
N_CARRIERS = 64
CP_LEN = 16
FS = 44100

# Audio Configuration
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = FS

def cofdm_demodulate(signal):
    """ Remove cyclic prefix and apply FFT """
    symbols = []
    
    for i in range(0, len(signal), N_CARRIERS + CP_LEN):
        if i + N_CARRIERS + CP_LEN > len(signal):
            break
        
        # Remove cyclic prefix
        ofdm_symbol = signal[i+CP_LEN:i+CP_LEN+N_CARRIERS]
        
        # Apply FFT
        freq_domain_signal = np.fft.fft(ofdm_symbol)
        symbols.append(freq_domain_signal.real)
    
    return np.array(symbols)

def decode_cofdm_symbols(symbols):
    """ Decode COFDM symbols back to bits """
    bits = []
    
    for symbol in symbols:
        bits.extend(['1' if x > 0 else '0' for x in symbol])
    
    return ''.join(bits)

def bits_to_text(bits):
    """ Convert binary string back to text """
    chars = [chr(int(bits[i:i+8], 2)) for i in range(0, len(bits), 8)]
    return ''.join(chars)

def receive_audio():
    """ Capture audio from 3.5mm jack and process it """
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    
    print("Listening for COFDM signal...")
    
    audio_data = []
    start_time = time.time()
    
    while time.time() - start_time < 5:  # Capture for 5 seconds
        data = stream.read(CHUNK)
        audio_data.extend(struct.unpack(str(CHUNK) + 'h', data))
    
    stream.stop_stream()
    stream.close()
    p.terminate()

    return np.array(audio_data) / 32768.0  # Normalize audio

if __name__ == "__main__":
    audio_signal = receive_audio()
    
    print("Processing received signal...")
    cofdm_symbols = cofdm_demodulate(audio_signal)
    received_bits = decode_cofdm_symbols(cofdm_symbols)
    decoded_text = bits_to_text(received_bits)
    
    print(f"Received Text: {decoded_text}")
