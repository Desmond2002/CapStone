#!/usr/bin/env python3
"""
Baofeng UV-5R Data Transmitter
Sends data through the USB programming cable's COM port.
"""

import serial
import time
import random
from datetime import datetime
import serial.tools.list_ports

class BaofengDataTransmitter:
    def __init__(self, com_port='COM5', baud_rate=110):
        """
        Initialize the transmitter using serial communication.
        
        Args:
            com_port: COM port for the USB programming cable
            baud_rate: Baud rate for serial communication
        """
        self.com_port = com_port
        self.baud_rate = baud_rate
        self.ser = None
        
    def list_com_ports(self):
        """List available COM ports and let user select one."""
        ports = list(serial.tools.list_ports.comports())
        
        if not ports:
            print("No COM ports found. Please check your USB programming cable connection.")
            return None
        
        print("Available COM ports:")
        for i, port in enumerate(ports):
            print(f"{i}: {port.device} - {port.description}")
        
        print("\nEnter the number for your Baofeng programming cable:")
        try:
            selection = int(input("> "))
            if 0 <= selection < len(ports):
                return ports[selection].device
            else:
                print("Invalid selection. Using first available port.")
                return ports[0].device
        except ValueError:
            print("Invalid input. Using first available port.")
            return ports[0].device
            
    def open_connection(self):
        """Open serial connection to the radio."""
        if not self.com_port:
            self.com_port = self.list_com_ports()
            
        if not self.com_port:
            print("No COM port selected. Exiting.")
            return False
            
        try:
            self.ser = serial.Serial(
                port=self.com_port,
                baudrate=self.baud_rate,
                timeout=1
            )
            print(f"Connected to {self.com_port} at {self.baud_rate} baud")
            return True
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            return False
            
    def close_connection(self):
        """Close the serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Connection closed")
            
    def transmit_data(self, data):
        """Transmit data through the serial port."""
        if not self.ser or not self.ser.is_open:
            if not self.open_connection():
                return False
                
        print(f"Transmitting: {data}")
        try:
            # Send data with proper encoding and termination
            self.ser.write((data + '\r\n').encode('utf-8'))
            
            # Read acknowledgment (if any)
            response = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if response:
                print(f"Response received: {response}")
                
            return True
        except serial.SerialException as e:
            print(f"Error transmitting data: {e}")
            return False

def simulate_temperature():
    """Generate a simulated temperature reading."""
    base_temp = 22.0  # 22Â°C base temperature
    variation = random.uniform(-1.0, 1.0)
    return base_temp + variation

def main():
    transmitter = BaofengDataTransmitter()
    
    if not transmitter.open_connection():
        print("Failed to open serial connection. Exiting.")
        return
    
    try:
        while True:
            # Simulate temperature reading
            temp = simulate_temperature()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data = f"TEMP:{temp:.2f}C,TIME:{timestamp}"
            
            # Transmit the data
            transmitter.transmit_data(data)
            
            # Wait before sending next reading
            print("Waiting 5 seconds before next transmission...")
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\nTransmission stopped by user")
    finally:
        transmitter.close_connection()

if __name__ == "__main__":
    main()