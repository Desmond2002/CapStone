import numpy as np
import sounddevice as sd
import time
from datetime import datetime, timedelta
import random
import json
import os
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading

# Configuration - Adjust these values
DEFAULT_DEVICE_ID = "43"  # Default device identifier
DEFAULT_INTERVAL = 60     # Default transmission interval (seconds)

MORSE_CODE = {
    '0': '-', '1': '.', '2': '.-', '3': '..-', '4': '...-',
    '5': '....-', '6': '-....', '7': '-.-', '8': '--.', 
    '9': '---', '#': '-...-'
}

# Transmission timing (seconds)
dot_duration = 0.2
dash_duration = 0.6
inter_symbol_pause = dot_duration
inter_char_pause = 3 * dot_duration

PREVIOUS_READINGS_FILE = "sender_previous_readings.json"

# Color functions for sensor values
def co_color(v):
    return "green" if v < 30 else ("orange" if v < 70 else "red")

def temp_color(v):
    return "blue" if v < 10 else ("green" if v < 30 else "red")

def pm_color(v, low=10, med=25):
    return "green" if v < low else ("orange" if v < med else "red")

class SensorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sensor Transmission GUI")
        self.root.geometry("1200x850")
        self.root.resizable(True, True)
        
        # Configure style
        self.configure_styles()
        
        # Set up variables
        self.device_id_var = tk.StringVar(value=DEFAULT_DEVICE_ID)
        self.transmission_interval_var = tk.IntVar(value=DEFAULT_INTERVAL)
        
        # Sensor value variables
        self.co_var = tk.DoubleVar(value=0)
        self.temperature_var = tk.DoubleVar(value=20)
        self.pm1_var = tk.DoubleVar(value=0)
        self.pm2_5_var = tk.DoubleVar(value=0)
        self.pm4_var = tk.DoubleVar(value=0)
        self.pm10_var = tk.DoubleVar(value=0)
        
        # Progress bar variables
        self.co_progress = tk.DoubleVar(value=0)
        self.temp_progress = tk.DoubleVar(value=20)
        self.pm1_progress = tk.DoubleVar(value=0)
        self.pm2_5_progress = tk.DoubleVar(value=0)
        self.pm4_progress = tk.DoubleVar(value=0)
        self.pm10_progress = tk.DoubleVar(value=0)
        
        # Override checkboxes variables
        self.override_co = tk.BooleanVar(value=False)
        self.override_temp = tk.BooleanVar(value=False)
        self.override_pm1 = tk.BooleanVar(value=False)
        self.override_pm2_5 = tk.BooleanVar(value=False)
        self.override_pm4 = tk.BooleanVar(value=False)
        self.override_pm10 = tk.BooleanVar(value=False)
        
        # Running state
        self.is_running = False
        self.transmission_thread = None
        self.next_transmission_time = None
        self.prev_readings = self.load_previous_readings()
        
        # Status variables
        self.status_text = tk.StringVar(value="Ready to transmit")
        self.next_tx_text = tk.StringVar(value="Not scheduled")
        self.last_message = tk.StringVar(value="")
        self.last_morse = tk.StringVar(value="")
        
        # Transmission stats
        self.total_transmissions = 0
        self.success_rate = tk.StringVar(value="100%")
        self.last_tx_time = "Never"

        # Transmission indicator
        self.current_morse = tk.StringVar(value="")
        self.transmitting = False
        
        # Create the GUI components
        self.create_widgets()
        
        # Initialize sliders with previous readings
        self.update_sliders_from_readings()
        
        # Connect slider change events
        self.connect_slider_callbacks()

    def configure_styles(self):
        style = ttk.Style()
        style.configure("TLabel", font=("Arial", 12))
        style.configure("TButton", font=("Arial", 12, "bold"))
        style.configure("Large.TButton", font=("Arial", 14, "bold"))
        style.configure("TCheckbutton", font=("Arial", 12))  # Configure style for checkbuttons
        style.configure("TLabelframe.Label", font=("Arial", 12, "bold"))
        
        # Progress bar styles
        style.configure("green.Horizontal.TProgressbar", background='green')
        style.configure("orange.Horizontal.TProgressbar", background='orange')
        style.configure("red.Horizontal.TProgressbar", background='red')
        style.configure("blue.Horizontal.TProgressbar", background='blue')
        
        # Create a bold version of the checkbutton
        style.configure("Bold.TCheckbutton", font=("Arial", 12, "bold"))

    def create_widgets(self):
        # Main frame using a grid layout to organize the content
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Split into two main columns
        main_frame.columnconfigure(0, weight=1)  # Left side
        main_frame.columnconfigure(1, weight=1)  # Right side
        
        # --- LEFT COLUMN: Configuration and Transmission Info ---
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configuration frame
        config_frame = ttk.LabelFrame(left_frame, text="Configuration", padding="10")
        config_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Device ID and interval
        config_grid = ttk.Frame(config_frame)
        config_grid.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(config_grid, text="Device ID:", font=("Arial", 14)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        device_entry = ttk.Entry(config_grid, textvariable=self.device_id_var, width=10, font=("Arial", 14))
        device_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(config_grid, text="Transmission Interval (sec):", font=("Arial", 14)).grid(
            row=0, column=2, sticky=tk.W, padx=(20, 5), pady=5)
        interval_spinbox = ttk.Spinbox(config_grid, from_=1, to=3600, textvariable=self.transmission_interval_var, 
                                      width=5, font=("Arial", 14))
        interval_spinbox.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
        # Message frame for last transmission
        message_frame = ttk.LabelFrame(left_frame, text="Last Transmitted Message", padding="10")
        message_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Transmitted message
        ttk.Label(message_frame, text="Encoded:", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(message_frame, textvariable=self.last_message, font=("Courier", 16, "bold")).pack(fill=tk.X, pady=2)
        
        # Morse code
        ttk.Label(message_frame, text="Morse Code:", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        morse_frame = ttk.Frame(message_frame)
        morse_frame.pack(fill=tk.X, expand=True, padx=5, pady=5)
        
        self.morse_display = scrolledtext.ScrolledText(morse_frame, height=4, font=("Courier", 14), wrap=tk.WORD)
        self.morse_display.pack(fill=tk.BOTH, expand=True)
        
        # Status indicator
        status_frame = ttk.Frame(message_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        # Transmission indicator (red dot when transmitting)
        self.tx_indicator = ttk.Label(status_frame, text="○", foreground="gray", font=("Arial", 24))
        self.tx_indicator.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(status_frame, text="Transmitting", font=("Arial", 14)).pack(side=tk.LEFT)
        
        # Current symbol display
        symbol_frame = ttk.Frame(message_frame)
        symbol_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(symbol_frame, text="Current Symbol:", font=("Arial", 14)).pack(side=tk.LEFT)
        ttk.Label(symbol_frame, textvariable=self.current_morse, font=("Courier", 16, "bold")).pack(side=tk.LEFT, padx=10)
        
        # Transmission history frame
        history_frame = ttk.LabelFrame(left_frame, text="Transmission History", padding="10")
        history_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Transmission display
        self.history_display = scrolledtext.ScrolledText(history_frame, height=6, width=40, font=("Courier", 12))
        self.history_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Stats and control
        stats_frame = ttk.LabelFrame(left_frame, text="Statistics", padding="10")
        stats_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Statistics grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X, padx=5, pady=5)
        
        # Row 1
        ttk.Label(stats_grid, text="Total Transmissions:", font=("Arial", 12)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.total_tx_label = ttk.Label(stats_grid, text="0", font=("Arial", 12, "bold"))
        self.total_tx_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(stats_grid, text="Success Rate:", font=("Arial", 12)).grid(row=0, column=2, sticky=tk.W, padx=(20, 5), pady=2)
        self.success_rate_label = ttk.Label(stats_grid, textvariable=self.success_rate, font=("Arial", 12, "bold"))
        self.success_rate_label.grid(row=0, column=3, sticky=tk.W, padx=5, pady=2)
        
        # Row 2
        ttk.Label(stats_grid, text="Status:", font=("Arial", 12)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(stats_grid, textvariable=self.status_text, font=("Arial", 12, "bold")).grid(
            row=1, column=1, columnspan=3, sticky=tk.W, padx=5, pady=2)
        
        # Row 3 - Next Transmission Time (Emphasized)
        ttk.Label(stats_grid, text="Next Transmission:", font=("Arial", 14, "bold")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=10)
        ttk.Label(stats_grid, textvariable=self.next_tx_text, font=("Arial", 16, "bold")).grid(
            row=2, column=1, columnspan=3, sticky=tk.W, padx=5, pady=10)
        
        # Control buttons
        control_frame = ttk.Frame(stats_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Start/Stop button
        self.start_stop_button = ttk.Button(control_frame, text="Start Transmitting", 
                                          command=self.toggle_transmission, 
                                          style="Large.TButton")
        self.start_stop_button.pack(side=tk.LEFT, padx=5)
        
        # Transmit Once button
        self.transmit_once_button = ttk.Button(control_frame, text="Transmit Once", 
                                             command=self.transmit_once,
                                             style="Large.TButton")
        self.transmit_once_button.pack(side=tk.LEFT, padx=5)
        
        # --- RIGHT COLUMN: Sensor Controls & Values ---
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        # Sensor values frame with progress bars and overrides
        self.create_sensor_display(right_frame, "Carbon Monoxide", "co", self.co_var, self.co_progress, 
                                 self.override_co, "ppm", 0, 100, co_color)
        
        self.create_sensor_display(right_frame, "Temperature", "temperature", self.temperature_var, 
                                 self.temp_progress, self.override_temp, "°C", -40, 85, temp_color)
        
        self.create_sensor_display(right_frame, "PM1", "pm1", self.pm1_var, self.pm1_progress, 
                                 self.override_pm1, "μg/m³", 0, 50, pm_color)
        
        self.create_sensor_display(right_frame, "PM2.5", "pm2_5", self.pm2_5_var, self.pm2_5_progress, 
                                 self.override_pm2_5, "μg/m³", 0, 50, pm_color)
        
        self.create_sensor_display(right_frame, "PM4", "pm4", self.pm4_var, self.pm4_progress, 
                                 self.override_pm4, "μg/m³", 0, 100, 
                                 lambda v: pm_color(v, 20, 50))
        
        self.create_sensor_display(right_frame, "PM10", "pm10", self.pm10_var, self.pm10_progress, 
                                 self.override_pm10, "μg/m³", 0, 100, 
                                 lambda v: pm_color(v, 20, 50))

    def create_sensor_display(self, parent, title, key, value_var, progress_var, override_var, unit, min_val, max_val, color_func):
        """Create a sensor display panel with slider, progress bar, and override checkbox"""
        # Create frame
        frame = ttk.LabelFrame(parent, text=title, padding="10")
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Top row - value display and unit
        value_frame = ttk.Frame(frame)
        value_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create a custom StringVar to format the value display
        formatted_value = tk.StringVar()
        self.update_formatted_value(formatted_value, value_var.get(), color_func)
        
        # Large value display
        value_label = ttk.Label(value_frame, textvariable=formatted_value, font=("Arial", 36, "bold"))
        value_label.pack(side=tk.LEFT, padx=10)
        
        # Connect the formatter to the value variable
        def update_value(*args):
            self.update_formatted_value(formatted_value, value_var.get(), color_func)
            # Update progress bar
            progress_var.set(value_var.get())
        
        value_var.trace_add("write", update_value)
        
        # Unit display
        unit_label = ttk.Label(value_frame, text=unit, font=("Arial", 14))
        unit_label.pack(side=tk.LEFT, padx=5, pady=10)
        
        # Override checkbox - Fixed: using style instead of direct font parameter
        override_check = ttk.Checkbutton(value_frame, text="Override", variable=override_var, 
                                       style="Bold.TCheckbutton")
        override_check.pack(side=tk.RIGHT, padx=20)
        
        # Middle row - progress bar
        progress_frame = ttk.Frame(frame)
        progress_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Progress bar
        progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=max_val-min_val, 
                                     length=200, style="green.Horizontal.TProgressbar")
        progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        # Store reference to update bar style
        setattr(self, f"{key}_bar", progress_bar)
        
        # Slider row
        slider_frame = ttk.Frame(frame)
        slider_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Min label
        ttk.Label(slider_frame, text=f"{min_val}", font=("Arial", 10)).pack(side=tk.LEFT)
        
        # Create slider
        slider = ttk.Scale(slider_frame, from_=min_val, to=max_val, variable=value_var, 
                          orient=tk.HORIZONTAL, length=300)
        slider.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        
        # Max label
        ttk.Label(slider_frame, text=f"{max_val}", font=("Arial", 10)).pack(side=tk.RIGHT)

    def update_formatted_value(self, formatted_var, value, color_func):
        """Update a formatted value display with color coding"""
        formatted_var.set(f"{value:.1f}")
        
        # Store color information for later use
        color = color_func(value)
        
        # Can't directly change the color of a ttk.Label through textvariable
        # We'll update the progress bar color instead
        return color

    def update_progress_bar_colors(self):
        """Update progress bar colors based on current values"""
        self.update_single_bar("co", co_color)
        self.update_single_bar("temperature", temp_color)
        self.update_single_bar("pm1", pm_color)
        self.update_single_bar("pm2_5", pm_color)
        self.update_single_bar("pm4", lambda v: pm_color(v, 20, 50))
        self.update_single_bar("pm10", lambda v: pm_color(v, 20, 50))

    def update_single_bar(self, key, color_func):
        """Update a single progress bar's color"""
        value_var = getattr(self, f"{key}_var")
        bar = getattr(self, f"{key}_bar")
        
        color = color_func(value_var.get())
        style = f"{color}.Horizontal.TProgressbar"
        bar.configure(style=style)

    def connect_slider_callbacks(self):
        """Connect callbacks to sliders and override checkboxes"""
        # For each sensor pair the value variable with its override
        value_override_pairs = [
            (self.co_var, self.override_co, "co"),
            (self.temperature_var, self.override_temp, "temperature"),
            (self.pm1_var, self.override_pm1, "pm1"),
            (self.pm2_5_var, self.override_pm2_5, "pm2_5"),
            (self.pm4_var, self.override_pm4, "pm4"),
            (self.pm10_var, self.override_pm10, "pm10")
        ]
        
        # Connect callbacks
        for value_var, override_var, key in value_override_pairs:
            # When value changes, update progress bar colors
            value_var.trace_add("write", lambda *args: self.update_progress_bar_colors())
            # When override changes, update the display
            override_var.trace_add("write", lambda *args, k=key: self.update_override_indicator(k))

    def update_override_indicator(self, key):
        """Update visual indicators when override status changes"""
        # This method can be expanded if needed
        self.update_progress_bar_colors()
    
    def toggle_transmission(self):
        if self.is_running:
            self.is_running = False
            self.start_stop_button.config(text="Start Transmitting")
            self.status_text.set("Transmission stopped")
            self.next_tx_text.set("Not scheduled")
            self.tx_indicator.config(foreground="gray", text="○")
        else:
            self.is_running = True
            self.start_stop_button.config(text="Stop Transmitting")
            self.status_text.set("Scheduling first transmission...")
            
            # Schedule first transmission immediately
            self.next_transmission_time = time.time()
            self.update_next_tx_time()
            
            # Start transmission in a separate thread
            self.transmission_thread = threading.Thread(target=self.transmission_loop)
            self.transmission_thread.daemon = True
            self.transmission_thread.start()
    
    def update_next_tx_time(self):
        """Update the next transmission time display"""
        if self.next_transmission_time and self.is_running:
            next_time = datetime.fromtimestamp(self.next_transmission_time).strftime("%H:%M:%S")
            countdown = max(0, int(self.next_transmission_time - time.time()))
            self.next_tx_text.set(f"{next_time} (in {countdown} seconds)")
            
            # Schedule another update in 1 second if we're still running
            if self.is_running:
                self.root.after(1000, self.update_next_tx_time)
    
    def transmission_loop(self):
        """Periodic transmission loop that runs on a fixed schedule"""
        while self.is_running:
            current_time = time.time()
            
            # If it's time for the next transmission
            if current_time >= self.next_transmission_time:
                # Transmit the data
                self.transmit_data()
                
                # Schedule next transmission on a fixed interval
                interval = self.transmission_interval_var.get()
                self.next_transmission_time = self.next_transmission_time + interval
                
                # If we're behind schedule, catch up
                if self.next_transmission_time <= current_time:
                    self.next_transmission_time = current_time + interval
                
                self.update_next_tx_time()
            
            # Small sleep to avoid CPU spinning
            time.sleep(0.1)
    
    def transmit_once(self):
        """Manually transmit once without affecting the schedule"""
        # Create a separate thread for the transmission
        thread = threading.Thread(target=self.transmit_data)
        thread.daemon = True
        thread.start()
    
    def update_transmission_animation(self, state=True, symbol=None):
        """Update the transmission animation indicators"""
        if state:
            # Transmitting
            self.tx_indicator.config(foreground="red", text="●")
            if symbol:
                self.current_morse.set(symbol)
        else:
            # Not transmitting
            self.tx_indicator.config(foreground="gray", text="○")
            self.current_morse.set("")
    
    def transmit_data(self):
        """Transmit the current sensor data"""
        self.transmitting = True
        self.status_text.set("Transmitting...")
        self.update_transmission_animation(True)
        
        # Generate sensor data with potential overrides
        sensor_data = self.generate_sensor_data()
        scaled = self.scale_sensor_data(sensor_data)
        
        # Save the readings (whether random or overridden)
        self.save_previous_readings(sensor_data)
        
        # Update progress bar colors
        self.update_progress_bar_colors()
        
        # Get device ID from the entry field
        device_id = self.device_id_var.get()
        
        # Calculate packet number
        now = datetime.now()
        midnight = now.replace(hour=0, minute=0, second=0)
        packet_num = (now - midnight).seconds // self.transmission_interval_var.get()
        
        # Format the data string
        data_str = (
            device_id +
            f"{packet_num:04d}" +
            scaled["co"] +
            scaled["temp"] +
            scaled["pm1"] +
            scaled["pm2_5"] +
            scaled["pm4"] +
            scaled["pm10"]
        )
        
        # Calculate checksum
        checksum = sum(int(c) for c in data_str) % 10
        full_msg = f"#{data_str}{checksum}#"
        
        # Update the UI with the message
        self.last_message.set(full_msg)
        morse_text = " ".join([MORSE_CODE[c] for c in full_msg])
        self.morse_display.delete(1.0, tk.END)
        self.morse_display.insert(tk.END, morse_text)
        
        # Add to transmission history
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.add_to_history(f"[{timestamp}] {full_msg}")
        
        # Update statistics
        self.total_transmissions += 1
        self.total_tx_label.config(text=str(self.total_transmissions))
        self.last_tx_time = timestamp
        
        print(f"\nEncoded: {full_msg}")
        print("Morse:", morse_text)
        
        # Transmit the message
        start_time = time.time()
        for c in full_msg:
            code = MORSE_CODE.get(c, '')
            if code:
                # For each dot/dash in the code, visualize it
                for symbol in code:
                    self.update_transmission_animation(True, symbol)
                    self.play_morse(symbol)
                    self.update_transmission_animation(False)
                    time.sleep(inter_symbol_pause)
                time.sleep(inter_char_pause)
        
        tx_time = time.time() - start_time
        print(f"Transmitted in {tx_time:.2f}s")
        self.status_text.set(f"Last transmission completed in {tx_time:.2f}s")
        
        self.transmitting = False
        self.update_transmission_animation(False)
    
    def add_to_history(self, message):
        """Add a message to the transmission history display"""
        self.history_display.insert(tk.END, message + "\n")
        self.history_display.see(tk.END)  # Auto-scroll to the end
    
    def generate_sensor_data(self):
        """Generate sensor data, using overrides where specified"""
        new_data = {}
        
        # For each sensor, either use the override value or generate a random one
        if self.override_co.get():
            new_data["co"] = self.co_var.get()
        else:
            new_data["co"] = max(0, min(self.prev_readings["co"] + random.uniform(-0.5, 1.0), 99))
            # Update the slider to show the new random value
            self.co_var.set(new_data["co"])
            
        if self.override_temp.get():
            new_data["temperature"] = self.temperature_var.get()
        else:
            new_data["temperature"] = max(-40, min(self.prev_readings["temperature"] + random.uniform(-0.5, 0.5), 85))
            self.temperature_var.set(new_data["temperature"])
            
        if self.override_pm1.get():
            new_data["pm1"] = self.pm1_var.get()
        else:
            new_data["pm1"] = max(0, self.prev_readings["pm1"] + random.uniform(-0.5, 1.5))
            self.pm1_var.set(new_data["pm1"])
            
        if self.override_pm2_5.get():
            new_data["pm2_5"] = self.pm2_5_var.get()
        else:
            new_data["pm2_5"] = max(0, self.prev_readings["pm2_5"] + random.uniform(-0.5, 1.5))
            self.pm2_5_var.set(new_data["pm2_5"])
            
        if self.override_pm4.get():
            new_data["pm4"] = self.pm4_var.get()
        else:
            new_data["pm4"] = max(0, self.prev_readings["pm4"] + random.uniform(-5, 5))
            self.pm4_var.set(new_data["pm4"])
            
        if self.override_pm10.get():
            new_data["pm10"] = self.pm10_var.get()
        else:
            new_data["pm10"] = max(0, self.prev_readings["pm10"] + random.uniform(-0.5, 2.0))
            self.pm10_var.set(new_data["pm10"])
            
        # Round all values to one decimal place
        return {k: round(v, 1) for k, v in new_data.items()}

    def scale_sensor_data(self, sensor_values):
        """Scale the sensor values to the correct format for transmission"""
        return {
            "co": f"{int(round(sensor_values['co'])):02d}",
            "temp": f"{int(round(sensor_values['temperature'])):02d}",
            "pm1": f"{int(round(sensor_values['pm1'])):02d}",
            "pm2_5": f"{int(round(sensor_values['pm2_5'] * 10)):03d}",
            "pm4": f"{int(round(sensor_values['pm4'])):03d}",
            "pm10": f"{int(round(sensor_values['pm10'])):02d}"
        }

    def update_sliders_from_readings(self):
        """Update the sliders to match the previous readings"""
        self.co_var.set(self.prev_readings["co"])
        self.temperature_var.set(self.prev_readings["temperature"])
        self.pm1_var.set(self.prev_readings["pm1"])
        self.pm2_5_var.set(self.prev_readings["pm2_5"])
        self.pm4_var.set(self.prev_readings["pm4"])
        self.pm10_var.set(self.prev_readings["pm10"])
        
        # Also update progress bars
        self.update_progress_bar_colors()
    
    def load_previous_readings(self):
        """Load previous sensor readings from file"""
        if os.path.exists(PREVIOUS_READINGS_FILE):
            try:
                with open(PREVIOUS_READINGS_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"co": 0, "temperature": 20, "pm1": 0, "pm2_5": 0, "pm4": 0, "pm10": 0}
    
    def save_previous_readings(self, prev):
        """Save sensor readings to file"""
        self.prev_readings = prev
        with open(PREVIOUS_READINGS_FILE, 'w') as f:
            json.dump(prev, f)
    
    def generate_tone(self, duration):
        """Generate a sine wave tone for Morse code transmission"""
        t = np.linspace(0, duration, int(44100 * duration), False)
        return 0.5 * np.sin(2 * np.pi * 800 * t)  # 800Hz frequency

    def play_morse(self, symbol):
        """Play a single Morse code symbol"""
        if symbol == '.':
            sd.play(self.generate_tone(dot_duration), samplerate=44100)
            sd.wait()
        elif symbol == '-':
            sd.play(self.generate_tone(dash_duration), samplerate=44100)
            sd.wait()

if __name__ == "__main__":
    root = tk.Tk()
    app = SensorGUI(root)
    root.mainloop()