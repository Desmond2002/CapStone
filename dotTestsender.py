import serial
import time

# Debugging function
def debug_log(message):
    print(f"[DEBUG] {message}")

# Serial Port Configuration
try:
    debug_log("Opening serial port at 110 baud...")
    ser = serial.Serial('/dev/tty.usbserial-130', baudrate=110, timeout=1)
    debug_log("Serial port opened successfully.")
except serial.SerialException:
    print("Error: Could not open serial port.")
    exit()

# Define the dot frequency (in Hz)
DOT_FREQUENCY = 800

# Calculate transmission time for commands at 110 baud
def calculate_transmission_time(command):
    # At 110 baud with 10 bits per byte (8 data + start + stop)
    # Each character takes approximately 1/11 seconds to transmit
    characters = len(command)
    transmission_time = (characters * 10) / 110  # in seconds
    return transmission_time

# Function to send a single dot with adjusted timing
def send_single_dot():
    debug_log("Preparing to send a single dot...")
    
    # Command to send
    command = f"SIGNAL {DOT_FREQUENCY}\r\n"
    
    # Calculate how long the command will take to transmit
    transmission_time = calculate_transmission_time(command)
    debug_log(f"Command transmission time: {transmission_time:.4f} seconds")
    
    # Send the dot frequency
    debug_log(f"Sending DOT signal: Frequency={DOT_FREQUENCY}Hz")
    ser.write(command.encode())
    ser.flush()
    
    # Wait for the command to fully transmit, plus the dot duration
    total_wait = transmission_time + 0.2  # Command time + standard dot duration
    debug_log(f"Waiting for {total_wait:.4f} seconds (transmission + dot duration)")
    time.sleep(total_wait)
    
    # Stop transmission
    stop_command = f"SIGNAL 0\r\n"
    stop_transmission_time = calculate_transmission_time(stop_command)
    debug_log(f"Sending STOP signal (transmission time: {stop_transmission_time:.4f} seconds)")
    ser.write(stop_command.encode())
    ser.flush()
    
    # Wait for stop command to fully transmit
    debug_log(f"Waiting for stop command to transmit: {stop_transmission_time:.4f} seconds")
    time.sleep(stop_transmission_time + 0.1)  # Extra time to ensure processing
    
    debug_log("Single dot transmission complete.")

if __name__ == "__main__":
    try:
        debug_log("Test program started.")
        send_single_dot()  # Send just one dot
        debug_log("Test completed successfully.")
    finally:
        # Make sure to stop any transmission and close properly
        debug_log("Ensuring all transmissions are stopped...")
        ser.write(f"SIGNAL 0\r\n".encode())
        ser.flush()
        time.sleep(1.0)  # Generous time to ensure final stop command is processed
        
        debug_log("Closing serial port...")
        ser.close()
        debug_log("Serial port closed.")