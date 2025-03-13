#!/usr/bin/env python3
"""
Simple Waveform Receiver - Records and visualizes audio signals
"""

import numpy as np
import matplotlib.pyplot as plt
import pyaudio
import time
import argparse
import threading
import os
from datetime import datetime
from scipy import signal

# Audio parameters
SAMPLE_RATE = 44100
CHUNK_SIZE = 1024
MAX_RECORD_SECONDS = 30  # Maximum recording time

class SimpleWaveformReceiver:
    def __init__(self):
        self.sample_rate = SAMPLE_RATE
        self.chunk_size = CHUNK_SIZE
        
        # For recording
        self.recording = []
        self.is_recording = False
        self.recording_start_time = None
        
        # For visualization
        self.plot_data = []
        self.max_plot_points = 100  # Number of chunks to display
        
        # Initialize PyAudio
        self.audio = pyaudio.PyAudio()
        self.stream = None
        
    def __del__(self):
        self.stop()
        if hasattr(self, 'audio'):
            self.audio.terminate()
    
    def start(self, device_index=None):
        """Start listening for audio"""
        # List available input devices
        print("\nAvailable audio input devices:")
        for i in range(self.audio.get_device_count()):
            dev_info = self.audio.get_device_info_by_index(i)
            if dev_info['maxInputChannels'] > 0:
                print(f"  [{i}] {dev_info['name']}")
        print()
        
        # Use default input device if none specified
        if device_index is None:
            try:
                default_device_info = self.audio.get_default_input_device_info()
                device_index = default_device_info['index']
                print(f"Using default input device: [{device_index}] {default_device_info['name']}")
            except:
                print("Could not determine default input device. Using system default.")
        
        # Start audio stream
        try:
            self.stream = self.audio.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )
            print("Audio stream opened successfully.")
            return True
        except Exception as e:
            print(f"Error opening audio stream: {e}")
            return False
    
    def stop(self):
        """Stop listening for audio"""
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            print("Audio stream stopped.")
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Process incoming audio data"""
        if status:
            print(f"Audio status: {status}")
        
        # Convert audio data
        audio_data = np.frombuffer(in_data, dtype=np.float32)
        
        # Calculate RMS level
        rms = np.sqrt(np.mean(audio_data**2))
        
        # Keep last data point for visualization
        self.plot_data.append((time.time(), audio_data.copy(), rms))
        if len(self.plot_data) > self.max_plot_points:
            self.plot_data.pop(0)
        
        # Add to recording if active
        if self.is_recording:
            self.recording.extend(audio_data)
            
            # Check if recording time exceeded
            if (time.time() - self.recording_start_time) > MAX_RECORD_SECONDS:
                print(f"Maximum recording time ({MAX_RECORD_SECONDS}s) reached.")
                self.stop_recording()
        
        return (None, pyaudio.paContinue)
    
    def start_recording(self, duration=0):
        """Begin recording audio"""
        if self.is_recording:
            print("Already recording!")
            return
        
        self.recording = []
        self.is_recording = True
        self.recording_start_time = time.time()
        
        # Auto-stop after duration (if specified)
        if duration > 0:
            threading.Thread(target=lambda: (
                time.sleep(duration),
                self.stop_recording() if self.is_recording else None
            )).start()
        
        print("Recording started...")
    
    def stop_recording(self):
        """Stop recording and save the data"""
        if not self.is_recording:
            print("Not currently recording!")
            return None
        
        self.is_recording = False
        duration = time.time() - self.recording_start_time
        
        if not self.recording:
            print("No recording data captured!")
            return None
        
        # Convert to numpy array
        recording_array = np.array(self.recording)
        
        # Create output directory if it doesn't exist
        os.makedirs("recordings", exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recordings/signal_{timestamp}.npz"
        
        # Save to file
        np.savez(filename, 
                 signal=recording_array,
                 sample_rate=self.sample_rate,
                 timestamp=timestamp)
        
        print(f"Recording saved to {filename} ({duration:.1f} seconds, {len(recording_array)} samples)")
        
        # Automatically analyze the recording
        self.analyze_recording(recording_array)
        
        return filename
    
    def analyze_recording(self, recording_data):
        """Analyze a recording and display visualizations"""
        if len(recording_data) == 0:
            print("No data to analyze")
            return
        
        duration = len(recording_data) / self.sample_rate
        
        # Create the plot
        plt.figure(figsize=(10, 8))
        
        # Time domain plot
        plt.subplot(3, 1, 1)
        t = np.linspace(0, duration, len(recording_data))
        plt.plot(t, recording_data, 'b-', linewidth=0.8)
        plt.title("Recorded Audio Signal")
        plt.xlabel("Time (s)")
        plt.ylabel("Amplitude")
        plt.grid(True, alpha=0.3)
        
        # Frequency domain plot
        plt.subplot(3, 1, 2)
        f, pxx = signal.welch(recording_data, self.sample_rate, nperseg=1024)
        plt.semilogy(f, pxx)
        plt.title("Power Spectrum")
        plt.xlabel("Frequency (Hz)")
        plt.ylabel("Power/Frequency")
        plt.grid(True, alpha=0.3)
        plt.xlim(0, 5000)  # Limit to audio range of interest
        
        # Spectrogram
        plt.subplot(3, 1, 3)
        frequencies, times, spectrogram = signal.spectrogram(
            recording_data, self.sample_rate, nperseg=512, noverlap=384
        )
        plt.pcolormesh(times, frequencies, 10 * np.log10(spectrogram + 1e-10), shading='gouraud')
        plt.title("Spectrogram")
        plt.ylabel("Frequency (Hz)")
        plt.xlabel("Time (s)")
        plt.ylim(0, 5000)
        plt.colorbar(label="Power (dB)")
        
        plt.tight_layout()
        plt.show()
        
        # Display summary info
        print("\nSignal Analysis:")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Peak amplitude: {np.max(np.abs(recording_data)):.4f}")
        print(f"RMS level: {np.sqrt(np.mean(recording_data**2)):.4f}")
        
        # Find dominant frequencies
        peak_indices = signal.find_peaks(pxx, height=np.max(pxx)/10)[0]
        peak_freqs = f[peak_indices]
        if len(peak_freqs) > 0:
            print(f"Dominant frequencies: {peak_freqs[0:5]} Hz")
    
    def analyze_file(self, filename):
        """Analyze a previously recorded signal file"""
        try:
            data = np.load(filename)
            signal_data = data['signal']
            sample_rate = data['sample_rate']
            timestamp = str(data.get('timestamp', 'unknown'))
            
            print(f"\nLoaded recording from {timestamp}")
            print(f"Sample rate: {sample_rate} Hz")
            print(f"Duration: {len(signal_data)/sample_rate:.2f} seconds")
            
            # Analyze the data
            self.analyze_recording(signal_data)
            
        except Exception as e:
            print(f"Error analyzing file: {e}")
    
    def run_interactive(self):
        """Run an interactive monitoring session"""
        print("\nInteractive Waveform Monitor")
        print("---------------------------")
        print("Commands:")
        print("  r - Start recording")
        print("  s - Stop recording")
        print("  v - View current audio levels")
        print("  q - Quit")
        print("---------------------------")
        
        signal_level = 0
        last_update = time.time()
        
        try:
            while True:
                # Update signal level periodically
                if time.time() - last_update >= 0.5:
                    if self.plot_data:
                        # Get most recent RMS level
                        signal_level = self.plot_data[-1][2]
                        
                        # Simple level meter
                        bars = int(signal_level * 50)
                        level_str = f"Signal level: [{'█' * bars}{' ' * (50-bars)}] {signal_level:.5f}"
                        
                        # Status indicator
                        if self.is_recording:
                            rec_time = time.time() - self.recording_start_time
                            status = f"RECORDING {rec_time:.1f}s"
                        else:
                            status = "MONITORING"
                            
                        # Clear previous line and print new
                        print(f"\r{status} - {level_str}", end="", flush=True)
                    
                    last_update = time.time()
                
                # Check for user input (non-blocking)
                if os.name == 'nt':  # Windows
                    import msvcrt
                    if msvcrt.kbhit():
                        key = msvcrt.getch().decode('utf-8').lower()
                        self._handle_key(key)
                else:  # Unix/Mac (requires simple non-blocking input method)
                    import sys, select
                    if select.select([sys.stdin], [], [], 0)[0]:
                        key = sys.stdin.read(1).lower()
                        self._handle_key(key)
                        
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nReceiver stopped.")
        finally:
            if self.is_recording:
                self.stop_recording()
    
    def _handle_key(self, key):
        """Handle key press events"""
        if key == 'r':
            if not self.is_recording:
                print("\nStarting recording...")
                self.start_recording()
            else:
                print("\nAlready recording!")
        elif key == 's':
            if self.is_recording:
                print("\nStopping recording...")
                self.stop_recording()
            else:
                print("\nNot currently recording!")
        elif key == 'v':
            print("\nGenerating visualization of current audio...")
            # Create a snapshot of recent data
            if self.plot_data:
                recent_data = np.concatenate([chunk[1] for chunk in self.plot_data[-20:]])
                self.analyze_recording(recent_data)
        elif key == 'q':
            print("\nQuitting...")
            self.stop()
            import sys
            sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Simple Waveform Receiver")
    
    parser.add_argument("-d", "--device", type=int, help="Audio input device index")
    parser.add_argument("-a", "--analyze", type=str, help="Analyze a saved recording file")
    parser.add_argument("-r", "--record", type=float, default=0, 
                       help="Record for specified duration in seconds (0 for manual control)")
    
    args = parser.parse_args()
    
    receiver = SimpleWaveformReceiver()
    
    # Analyze a file if specified
    if args.analyze:
        receiver.analyze_file(args.analyze)
        return
    
    # Otherwise start the receiver
    if receiver.start(args.device):
        # Start recording if duration specified
        if args.record > 0:
            receiver.start_recording(args.record)
            
        # Run interactive monitoring
        receiver.run_interactive()
        
        # Clean up
        receiver.stop()
    else:
        print("Failed to start audio capture!")

if __name__ == "__main__":
    main()
