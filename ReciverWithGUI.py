import numpy as np
import sounddevice as sd
import queue
import time
from datetime import datetime, timedelta
import requests
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading

# Configuration - Must match sender!
TRANSMISSION_INTERVAL = 1  # Minutes between transmissions

REVERSE_MORSE = {
    '-': '0', '.': '1', '.-': '2', '..-': '3',
    '...-': '4', '....-': '5', '-....': '6',
    '-.-': '7', '--.': '8', '---': '9',
    '-...-': '#'
}

# Receiver timing (match sender's dot duration)
dot_duration = 0.2
dash_duration = 0.6
dash_threshold = (dot_duration + dash_duration)/2
inter_char_pause = 0.6  # 2 * dot_duration
threshold = 0.05
debounce_count = 2

# Default API settings
DEFAULT_API_URL = "https://findthefrontier.ca/spark/data"

# Color functions for sensor values
def co_color(v):
    return "green" if v < 30 else ("orange" if v < 70 else "red")

def temp_color(v):
    return "blue" if v < 10 else ("green" if v < 30 else "red")

def pm_color(v, low=10, med=25):
    return "green" if v < low else ("orange" if v < med else "red")

class ReceiverGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Morse Signal Receiver")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Configure style
        self.configure_styles()
        
        # Set up variables
        self.is_running = False
        self.audio_queue = queue.Queue()
        self.current_symbol = ''
        self.current_message = []
        self.recording = False
        
        # Settings variables
        self.threshold_var = tk.DoubleVar(value=threshold)
        self.post_to_api_var = tk.BooleanVar(value=False)
        self.api_url = tk.StringVar(value=DEFAULT_API_URL)
        
        # Statistics
        self.total_receptions = 0
        self.successful_receptions = 0
        self.success_rate = tk.StringVar(value="0%")
        self.last_reception_time = tk.StringVar(value="Never")
        self.received_chars = []
        
        # Sensor data
        self.sensor_data = {
            "device_id": "N/A",
            "packet_num": 0,
            "carbon_monoxide_ppm": 0,
            "temperature_celcius": 0,
            "pm1_ug_m3": 0,
            "pm2_5_ug_m3": 0,
            "pm4_ug_m3": 0,
            "pm10_ug_m3": 0,
            "timestamp": "N/A"
        }
        
        # Status variables
        self.status_text = tk.StringVar(value="Ready")
        
        # Create the UI components
        self.create_widgets()
        
    def configure_styles(self):
        style = ttk.Style()
        style.configure("TLabel", font=("Arial", 12))
        style.configure("TButton", font=("Arial", 12, "bold"))
        style.configure("Large.TButton", font=("Arial", 14, "bold"))
        style.configure("TCheckbutton", font=("Arial", 12))  
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
        
        # --- LEFT COLUMN: Decoding and Reception Info ---
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configuration frame
        config_frame = ttk.LabelFrame(left_frame, text="Configuration", padding="10")
        config_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Settings grid
        settings_grid = ttk.Frame(config_frame)
        settings_grid.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(settings_grid, text="Detection Threshold:", font=("Arial", 14)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        threshold_spin = ttk.Spinbox(settings_grid, from_=0.01, to=0.5, increment=0.01, textvariable=self.threshold_var, 
                                    width=5, font=("Arial", 14))
        threshold_spin.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # API settings
        ttk.Label(settings_grid, text="Post to API:", font=("Arial", 14)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        api_check = ttk.Checkbutton(settings_grid, variable=self.post_to_api_var, style="Bold.TCheckbutton")
        api_check.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(settings_grid, text="API URL:", font=("Arial", 14)).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        api_entry = ttk.Entry(settings_grid, textvariable=self.api_url, width=30, font=("Arial", 14))
        api_entry.grid(row=2, column=1, columnspan=3, sticky=tk.EW, padx=5, pady=5)
        
        # Decoding visualization frame
        decode_frame = ttk.LabelFrame(left_frame, text="Decoding Process", padding="10")
        decode_frame.pack(fill=tk.X, padx=5, pady=5)  # Changed from fill=tk.BOTH to fill=tk.X to reduce vertical space
        
        # Current Morse symbols being built
        morse_display_frame = ttk.Frame(decode_frame)
        morse_display_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(morse_display_frame, text="Current Symbol:", font=("Arial", 14)).pack(side=tk.LEFT)
        self.morse_symbol_var = tk.StringVar(value="")
        ttk.Label(morse_display_frame, textvariable=self.morse_symbol_var, 
                 font=("Courier", 16, "bold")).pack(side=tk.LEFT, padx=10)
        
        # Recording indicator
        self.recording_indicator = ttk.Label(morse_display_frame, text="○", foreground="gray", font=("Arial", 24))
        self.recording_indicator.pack(side=tk.RIGHT, padx=10)
        
        ttk.Label(morse_display_frame, text="Recording", font=("Arial", 14)).pack(side=tk.RIGHT)
        
        # Message buffer display (scrollable) - REDUCED HEIGHT from 6 to 4
        ttk.Label(decode_frame, text="Message Buffer:", font=("Arial", 14)).pack(anchor=tk.W, padx=5)
        self.buffer_display = scrolledtext.ScrolledText(decode_frame, height=4, width=40, font=("Courier", 14))
        self.buffer_display.pack(fill=tk.X, padx=5, pady=5)  # Changed from fill=tk.BOTH, expand=True to just fill=tk.X
        
        # Last complete message (made more compact)
        message_frame = ttk.Frame(decode_frame)
        message_frame.pack(fill=tk.X, padx=5, pady=2)  # Reduced padding
        
        ttk.Label(message_frame, text="Last Complete Message:", font=("Arial", 14)).pack(side=tk.LEFT)
        self.complete_message_var = tk.StringVar(value="None received yet")
        ttk.Label(message_frame, textvariable=self.complete_message_var, 
                font=("Courier", 14)).pack(side=tk.LEFT, padx=10)
        
        # Stats and control
        stats_frame = ttk.LabelFrame(left_frame, text="Statistics", padding="10")
        stats_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Statistics grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X, padx=5, pady=5)
        
        # Row 1
        ttk.Label(stats_grid, text="Total Receptions:", font=("Arial", 12)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.total_rx_label = ttk.Label(stats_grid, text="0", font=("Arial", 12, "bold"))
        self.total_rx_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(stats_grid, text="Successful:", font=("Arial", 12)).grid(row=0, column=2, sticky=tk.W, padx=(20, 5), pady=2)
        self.success_rx_label = ttk.Label(stats_grid, text="0", font=("Arial", 12, "bold"))
        self.success_rx_label.grid(row=0, column=3, sticky=tk.W, padx=5, pady=2)
        
        # Row 2
        ttk.Label(stats_grid, text="Success Rate:", font=("Arial", 12)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.success_rate_label = ttk.Label(stats_grid, textvariable=self.success_rate, font=("Arial", 12, "bold"))
        self.success_rate_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(stats_grid, text="Last Reception:", font=("Arial", 12)).grid(row=1, column=2, sticky=tk.W, padx=(20, 5), pady=2)
        self.last_rx_label = ttk.Label(stats_grid, textvariable=self.last_reception_time, font=("Arial", 12, "bold"))
        self.last_rx_label.grid(row=1, column=3, sticky=tk.W, padx=5, pady=2)
        
        # Row 3
        ttk.Label(stats_grid, text="Status:", font=("Arial", 12)).grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(stats_grid, textvariable=self.status_text, font=("Arial", 12, "bold")).grid(
            row=2, column=1, columnspan=3, sticky=tk.W, padx=5, pady=2)
        
        # Control buttons - Moved up in the layout order
        control_frame = ttk.Frame(stats_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Start/Stop button
        self.start_button = ttk.Button(control_frame, text="Start Listening", command=self.toggle_listening, 
                                     style="Large.TButton")
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        # --- RIGHT COLUMN: Sensor Data Display ---
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        # Device info frame
        device_frame = ttk.LabelFrame(right_frame, text="Device Information", padding="10")
        device_frame.pack(fill=tk.X, padx=5, pady=5)
        
        device_info = ttk.Frame(device_frame)
        device_info.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(device_info, text="Device ID:", font=("Arial", 14)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.device_id_var = tk.StringVar(value="N/A")
        ttk.Label(device_info, textvariable=self.device_id_var, font=("Arial", 20, "bold")).grid(
            row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(device_info, text="Raw ID:", font=("Arial", 14)).grid(row=0, column=2, sticky=tk.W, padx=(20, 5), pady=5)
        self.raw_id_var = tk.StringVar(value="N/A")
        ttk.Label(device_info, textvariable=self.raw_id_var, font=("Arial", 16)).grid(
            row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(device_info, text="Timestamp:", font=("Arial", 14)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.timestamp_var = tk.StringVar(value="N/A")
        ttk.Label(device_info, textvariable=self.timestamp_var, font=("Arial", 16)).grid(
            row=1, column=1, columnspan=3, sticky=tk.W, padx=5, pady=5)
        
        # Create sensor value displays
        self.create_sensor_display(right_frame, "Carbon Monoxide", "carbon_monoxide_ppm", "ppm", 0, 100, co_color)
        self.create_sensor_display(right_frame, "Temperature", "temperature_celcius", "°C", -40, 85, temp_color)
        self.create_sensor_display(right_frame, "PM1", "pm1_ug_m3", "μg/m³", 0, 50, pm_color)
        self.create_sensor_display(right_frame, "PM2.5", "pm2_5_ug_m3", "μg/m³", 0, 50, pm_color)
        self.create_sensor_display(right_frame, "PM4", "pm4_ug_m3", "μg/m³", 0, 100, lambda v: pm_color(v, 20, 50))
        self.create_sensor_display(right_frame, "PM10", "pm10_ug_m3", "μg/m³", 0, 100, lambda v: pm_color(v, 20, 50))

    def create_sensor_display(self, parent, title, key, unit, min_val, max_val, color_func):
        """Create a display for a single sensor value with a gauge-like appearance"""
        frame = ttk.LabelFrame(parent, text=title, padding="10")
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Value display
        value_frame = ttk.Frame(frame)
        value_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Large value display
        value_var = tk.StringVar(value="0")
        value_label = ttk.Label(value_frame, textvariable=value_var, font=("Arial", 36, "bold"))
        value_label.pack(side=tk.LEFT, padx=10)
        
        # Unit display
        unit_label = ttk.Label(value_frame, text=unit, font=("Arial", 14))
        unit_label.pack(side=tk.LEFT, padx=5, pady=10)
        
        # Progress bar
        progress_var = tk.DoubleVar(value=0)
        progress_bar = ttk.Progressbar(frame, variable=progress_var, maximum=max_val-min_val, 
                                     length=200, style="green.Horizontal.TProgressbar")
        progress_bar.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Store references to update these components
        setattr(self, f"{key}_value", value_var)
        setattr(self, f"{key}_progress", progress_var)
        setattr(self, f"{key}_label", value_label)
        setattr(self, f"{key}_bar", progress_bar)
        setattr(self, f"{key}_color_func", color_func)

    def toggle_listening(self):
        if not self.is_running:
            self.start_listening()
            self.start_button.config(text="Stop Listening")
        else:
            self.stop_listening()
            self.start_button.config(text="Start Listening")
    
    def start_listening(self):
        self.is_running = True
        self.status_text.set("Initializing audio...")
        
        # Start audio capture in a separate thread
        self.listen_thread = threading.Thread(target=self.listen)
        self.listen_thread.daemon = True
        self.listen_thread.start()
        
        # Start audio processing in a separate thread
        self.process_thread = threading.Thread(target=self.process_audio)
        self.process_thread.daemon = True
        self.process_thread.start()
        
        self.status_text.set("Listening...")
    
    def stop_listening(self):
        self.is_running = False
        self.status_text.set("Stopped")
    
    def audio_callback(self, indata, frames, time, status):
        if self.is_running:
            self.audio_queue.put(indata.copy())
    
    def listen(self):
        try:
            with sd.InputStream(callback=self.audio_callback, samplerate=44100) as stream:
                device_info = f"Using {stream.device} at {stream.samplerate}Hz"
                self.root.after(0, lambda: self.status_text.set(device_info))
                print(device_info)
                
                while self.is_running:
                    time.sleep(0.1)
        except Exception as e:
            error_msg = f"Audio error: {str(e)}"
            print(error_msg)
            self.root.after(0, lambda: self.status_text.set(error_msg))
    
    def process_audio(self):
        in_signal = False
        signal_samples = 0
        last_signal_end = time.time()
        signal_start = 0
        current_symbol = ''
        
        while self.is_running:
            try:
                # Get audio data from the queue
                data = self.audio_queue.get_nowait().flatten()
                rms = np.sqrt(np.mean(data**2))
                
                now = time.time()
                current_threshold = self.threshold_var.get()
                
                if rms > current_threshold:
                    signal_samples += 1
                    if not in_signal and signal_samples >= debounce_count:
                        in_signal = True
                        signal_start = now
                        self.root.after(0, self.blink_recording_indicator)
                else:
                    signal_samples = 0
                    if in_signal:
                        in_signal = False
                        duration = now - signal_start
                        last_signal_end = now
                        
                        # Add to current symbol
                        symbol_part = '.' if duration < dash_threshold else '-'
                        current_symbol += symbol_part
                        
                        # Update UI with current symbol
                        self.root.after(0, lambda s=current_symbol: self.morse_symbol_var.set(s))
                
                if not in_signal and (now - last_signal_end) > inter_char_pause and current_symbol:
                    char = REVERSE_MORSE.get(current_symbol, '?')
                    print(f"{current_symbol} → {char}")
                    
                    # Process the character
                    self.root.after(0, lambda c=char: self.process_char(c))
                    
                    current_symbol = ''
                    self.root.after(0, lambda: self.morse_symbol_var.set(""))
            
            except queue.Empty:
                time.sleep(0.01)
            except Exception as e:
                print(f"Processing error: {str(e)}")
    
    def process_char(self, char):
        """Process a decoded character"""
        if char == '#':
            if not self.recording:
                # Start of message
                print("\n--- START ---")
                self.recording = True
                self.current_message = []
                self.recording_indicator.config(foreground="red", text="●")
            else:
                # End of message
                print("\n--- END ---")
                self.recording = False
                self.recording_indicator.config(foreground="gray", text="○")
                
                # Process the complete message
                if self.current_message:
                    msg = ''.join(self.current_message)
                    self.process_message(msg)
        elif self.recording:
            self.current_message.append(char)
            
        # Update the buffer display in the UI
        self.update_buffer_display(char)
    
    def update_buffer_display(self, char):
        """Update the buffer display with the latest character"""
        # Add the character to our tracking list
        self.received_chars.append(char)
        
        # Keep only the last 40 characters to avoid UI slowdowns
        if len(self.received_chars) > 40:  # Reduced from 50 to 40
            self.received_chars = self.received_chars[-40:]
        
        # Display the characters with formatting
        self.buffer_display.delete(1.0, tk.END)
        
        display_text = ""
        for c in self.received_chars:
            if c == '#':
                if self.recording:
                    display_text += "▶ "  # Start symbol
                else:
                    display_text += "■ "  # End symbol
            else:
                display_text += c + " "
        
        self.buffer_display.insert(tk.END, display_text)
        self.buffer_display.see(tk.END)  # Scroll to end
    
    def blink_recording_indicator(self):
        """Blink the recording indicator when a signal is detected"""
        if not self.is_running:
            return
            
        current_color = self.recording_indicator.cget("foreground")
        
        if self.recording:
            # When recording, blink between red and bright red
            new_color = "darkred" if current_color == "red" else "red"
        else:
            # When not recording, blink between gray and white
            new_color = "white" if current_color == "gray" else "gray"
        
        self.recording_indicator.config(foreground=new_color)
    
    def process_message(self, msg):
        """Process a complete message and update the UI with sensor data"""
        
        self.total_receptions += 1
        self.total_rx_label.config(text=str(self.total_receptions))
        
        # Update the complete message display
        self.complete_message_var.set(msg)
        
        try:
            if len(msg) != 21:
                print(f"Invalid length {len(msg)} (expected 21)")
                return
            
            # Calculate checksum
            calculated_checksum = sum(int(c) for c in msg[:20]) % 10
            received_checksum = int(msg[20])
            
            if calculated_checksum != received_checksum:
                print(f"Checksum mismatch (calculated {calculated_checksum}, received {received_checksum})")
                return
            
            # Valid message, process it
            self.successful_receptions += 1
            self.success_rx_label.config(text=str(self.successful_receptions))
            
            # Calculate success rate
            success_rate = (self.successful_receptions / self.total_receptions) * 100
            self.success_rate.set(f"{success_rate:.1f}%")
            
            # Parse the message
            raw_device_id = msg[0:2]
            formatted_device_id = f"SE{raw_device_id}0A"  # Format as requested
            
            payload = {
                "device_id": formatted_device_id,
                "raw_id": raw_device_id,
                "packet_num": int(msg[2:6]),
                "carbon_monoxide_ppm": int(msg[6:8]),
                "temperature_celcius": int(msg[8:10]),
                "pm1_ug_m3": int(msg[10:12]),
                "pm2_5_ug_m3": int(msg[12:15])/10.0,
                "pm4_ug_m3": int(msg[15:18]),
                "pm10_ug_m3": int(msg[18:20])
            }
            
            # Calculate timestamp
            midnight = datetime.now().replace(hour=0, minute=0, second=0)
            timestamp = midnight + timedelta(minutes=payload['packet_num']*TRANSMISSION_INTERVAL)
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            payload["timestamp"] = timestamp_str
            
            # Set last reception time
            self.last_reception_time.set(timestamp_str)
            
            # Update the UI with received data
            self.update_sensor_display(payload)
            
            print(f"\nValid Packet @ {timestamp_str}:")
            print(f"Device: {formatted_device_id} (Raw: {raw_device_id})")
            print(f"CO: {payload['carbon_monoxide_ppm']} ppm")
            print(f"Temp: {payload['temperature_celcius']}°C")
            print(f"PM1: {payload['pm1_ug_m3']} µg/m³")
            print(f"PM2.5: {payload['pm2_5_ug_m3']:.1f} µg/m³")
            print(f"PM4: {payload['pm4_ug_m3']} µg/m³")
            print(f"PM10: {payload['pm10_ug_m3']} µg/m³")
            
            # Post to API if enabled
            if self.post_to_api_var.get():
                api_data = {
                    "device_id": formatted_device_id,
                    "carbon_monoxide_ppm": payload['carbon_monoxide_ppm'],
                    "temperature_celcius": payload['temperature_celcius'],
                    "pm1_ug_m3": payload['pm1_ug_m3'],
                    "pm2_5_ug_m3": payload['pm2_5_ug_m3'],
                    "pm4_ug_m3": payload['pm4_ug_m3'],
                    "pm10_ug_m3": payload['pm10_ug_m3'],
                    "recorded_at": timestamp.isoformat()
                }
                try:
                    response = requests.post(self.api_url.get(), json=api_data)
                    self.status_text.set(f"API Status: {response.status_code}")
                    print(f"API Status: {response.status_code}")
                except Exception as e:
                    self.status_text.set(f"API Error: {str(e)}")
                    print(f"API Error: {str(e)}")
            
        except Exception as e:
            print(f"Processing error: {str(e)}")
            self.status_text.set(f"Processing error: {str(e)}")
    
    def update_sensor_display(self, payload):
        """Update the UI with the received sensor data"""
        # Update device info
        self.device_id_var.set(payload["device_id"])
        self.raw_id_var.set(payload["raw_id"])
        self.timestamp_var.set(payload["timestamp"])
        
        # Update each sensor value
        self.update_single_sensor("carbon_monoxide_ppm", payload["carbon_monoxide_ppm"])
        self.update_single_sensor("temperature_celcius", payload["temperature_celcius"])
        self.update_single_sensor("pm1_ug_m3", payload["pm1_ug_m3"])
        self.update_single_sensor("pm2_5_ug_m3", payload["pm2_5_ug_m3"])
        self.update_single_sensor("pm4_ug_m3", payload["pm4_ug_m3"])
        self.update_single_sensor("pm10_ug_m3", payload["pm10_ug_m3"])
    
    def update_single_sensor(self, key, value):
        """Update a single sensor's display"""
        # Get the variable references
        value_var = getattr(self, f"{key}_value")
        progress_var = getattr(self, f"{key}_progress")
        label = getattr(self, f"{key}_label")
        bar = getattr(self, f"{key}_bar")
        color_func = getattr(self, f"{key}_color_func")
        
        # Format the value (special case for PM2.5 which has decimal)
        if key == "pm2_5_ug_m3":
            value_var.set(f"{value:.1f}")
        else:
            value_var.set(str(value))
        
        # Update the progress bar
        progress_var.set(value)
        
        # Update the color based on the value
        color = color_func(value)
        bar.configure(style=f"{color}.Horizontal.TProgressbar")
    
    def on_closing(self):
        """Handle window closing"""
        self.stop_listening()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ReceiverGUI(root)
    root.mainloop()