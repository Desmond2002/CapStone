#!/usr/bin/env python3
"""
Morse Code Transmitter Application
---------------------------------
MacBook-to-MacBook Radio Communication using Morse Code

This application encodes text messages to Morse code audio signals for transmission
through Baofeng UV-5RX radios. The audio output connects from MacBook to the radio's
microphone port via a 3.5mm audio jack.
"""

import sys
import time
import numpy as np
import pyaudio
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                            QSpinBox, QSlider, QGroupBox, QMessageBox, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont


class MorseCode:
    """Morse code utility class for encoding."""
    
    # Standard Morse code mapping
    MORSE_CODE_DICT = {
        'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.', 
        'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..', 
        'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.', 
        'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 
        'Y': '-.--', 'Z': '--..', '1': '.----', '2': '..---', '3': '...--', 
        '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..',
        '9': '----.', '0': '-----', '.': '.-.-.-', ',': '--..--', '?': '..--..',
        "'": '.----.', '!': '-.-.--', '/': '-..-.', '(': '-.--.', ')': '-.--.-',
        '&': '.-...', ':': '---...', ';': '-.-.-.', '=': '-...-', '+': '.-.-.',
        '-': '-....-', '_': '..--.-', '"': '.-..-.', '$': '...-..-', '@': '.--.-.'
    }
    
    # Special procedural signals
    PROCEDURAL_SIGNALS = {
        'START_TRANSMISSION': '-.-.-',     # KA
        'END_TRANSMISSION': '.-.-.',       # AR
        'ERROR': '........',               # 8 dots
        'WAIT': '.-...',                   # AS
        'END_OF_WORK': '...-.-',           # SK
        'INVITATION_TO_TRANSMIT': '-.-'    # K
    }

    @classmethod
    def encode(cls, text):
        """Convert a text string to Morse code."""
        text = text.upper()
        morse_code = []
        
        for char in text:
            if char == ' ':
                # Add a word space
                morse_code.append('/')
            elif char in cls.MORSE_CODE_DICT:
                morse_code.append(cls.MORSE_CODE_DICT[char])
            # Skip characters not in dictionary
        
        return ' '.join(morse_code)
    
    @classmethod
    def get_timing_sequence(cls, morse_code, wpm=18):
        """
        Convert Morse code string to a timing sequence.
        Returns a list of (signal_state, duration) tuples where:
        - signal_state is True for mark (tone on) and False for space (tone off)
        - duration is in seconds
        
        WPM is calculated as PARIS takes 50 units, so:
        - At 1 WPM, dot duration = 1.2 seconds
        - At 18 WPM, dot duration = 1.2/18 = 0.0667 seconds
        """
        # Calculate dot duration based on WPM
        dot_duration = 1.2 / wpm
        
        timing = []
        for i, char in enumerate(morse_code):
            if char == '.':
                timing.append((True, dot_duration))
            elif char == '-':
                timing.append((True, 3 * dot_duration))
            elif char == ' ':
                # Space between characters (already added 1 unit after last symbol)
                timing.append((False, 2 * dot_duration))
            elif char == '/':
                # Word space (already added 1 unit after last symbol)
                timing.append((False, 6 * dot_duration))
            
            # Add inter-symbol space (except after spaces and at the end)
            if char not in [' ', '/'] and i < len(morse_code) - 1 and morse_code[i+1] not in [' ', '/']:
                timing.append((False, dot_duration))
                
        return timing


class MorseAudioGenerator:
    """Generates audio signals for Morse code transmission."""
    
    def __init__(self, tone_frequency=750, sample_rate=44100, volume=0.65):
        """
        Initialize the audio generator.
        
        Args:
            tone_frequency: Frequency of the Morse code tone in Hz
            sample_rate: Audio sample rate
            volume: Audio volume (0.0 to 1.0)
        """
        self.tone_frequency = tone_frequency
        self.sample_rate = sample_rate
        self.volume = volume
        self.p = pyaudio.PyAudio()
        self.stream = None
    
    def generate_tone(self, duration):
        """Generate a sine wave tone of the given duration in seconds."""
        t = np.linspace(0, duration, int(self.sample_rate * duration), False)
        # Apply a slight fade in/out to avoid clicks
        fade_duration = min(0.01, duration / 10)
        fade_samples = int(fade_duration * self.sample_rate)
        
        # Generate the base tone
        tone = np.sin(2 * np.pi * self.tone_frequency * t)
        
        # Apply fade in
        if fade_samples > 0:
            fade_in = np.linspace(0, 1, fade_samples)
            tone[:fade_samples] *= fade_in
            
            # Apply fade out
            fade_out = np.linspace(1, 0, fade_samples)
            tone[-fade_samples:] *= fade_out
        
        # Scale by volume
        return (tone * self.volume).astype(np.float32)
    
    def generate_silence(self, duration):
        """Generate silence of the given duration in seconds."""
        return np.zeros(int(self.sample_rate * duration), dtype=np.float32)
    
    def start_stream(self):
        """Open the audio output stream."""
        if self.stream is None or not self.stream.is_active():
            self.stream = self.p.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=self.sample_rate,
                output=True
            )
    
    def stop_stream(self):
        """Close the audio output stream."""
        if self.stream is not None and self.stream.is_active():
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
    
    def cleanup(self):
        """Cleanup resources."""
        self.stop_stream()
        self.p.terminate()
    
    def generate_preamble(self, duration=2.0, pattern_duration=0.1):
        """
        Generate a preamble to trigger VOX activation.
        Creates alternating tone/silence pattern.
        """
        segments = []
        t = 0
        while t < duration:
            segments.append(self.generate_tone(pattern_duration))
            segments.append(self.generate_silence(pattern_duration))
            t += 2 * pattern_duration
        
        return np.concatenate(segments)
    
    def play_timing_sequence(self, timing_sequence):
        """
        Play a timing sequence from MorseCode.get_timing_sequence().
        
        Args:
            timing_sequence: List of (signal_state, duration) tuples
        """
        self.start_stream()
        
        for signal_state, duration in timing_sequence:
            if signal_state:  # True for mark (tone)
                samples = self.generate_tone(duration)
            else:  # False for space (silence)
                samples = self.generate_silence(duration)
            
            self.stream.write(samples.tobytes())


class TransmissionProtocol:
    """Handles the Morse code transmission protocol."""
    
    def __init__(self, audio_generator, wpm=18):
        """
        Initialize the transmission protocol.
        
        Args:
            audio_generator: MorseAudioGenerator instance
            wpm: Words per minute speed
        """
        self.audio_generator = audio_generator
        self.wpm = wpm
        
    def transmit_message(self, message, redundancy=1):
        """
        Transmit a message using the defined protocol.
        
        Args:
            message: Text message to transmit
            redundancy: Number of times to repeat each character (for error correction)
        """
        # 1. Generate preamble to activate VOX
        preamble = self.audio_generator.generate_preamble(duration=1.5)
        self.audio_generator.start_stream()
        self.audio_generator.stream.write(preamble.tobytes())
        
        # 2. Add start marker
        start_marker = MorseCode.PROCEDURAL_SIGNALS['START_TRANSMISSION']
        start_timing = MorseCode.get_timing_sequence(start_marker, self.wpm)
        self.audio_generator.play_timing_sequence(start_timing)
        
        # Small pause after start marker
        time.sleep(0.5)
        
        # 3. Encode and transmit the message with redundancy
        if redundancy > 1:
            # Apply character-by-character redundancy
            redundant_message = ''
            for char in message:
                redundant_message += char * redundancy
                if char != ' ':  # Don't add extra space after spaces
                    redundant_message += ' '
            morse_message = MorseCode.encode(redundant_message)
        else:
            morse_message = MorseCode.encode(message)
            
        message_timing = MorseCode.get_timing_sequence(morse_message, self.wpm)
        self.audio_generator.play_timing_sequence(message_timing)
        
        # 4. Add end marker
        end_marker = MorseCode.PROCEDURAL_SIGNALS['END_TRANSMISSION']
        end_timing = MorseCode.get_timing_sequence(end_marker, self.wpm)
        self.audio_generator.play_timing_sequence(end_timing)
        
        # Close the stream
        self.audio_generator.stop_stream()


class TransmissionWorker(QThread):
    """Worker thread for sending transmission without blocking the UI."""
    finished = pyqtSignal()
    status_update = pyqtSignal(str)
    
    def __init__(self, protocol, message, redundancy):
        super().__init__()
        self.protocol = protocol
        self.message = message
        self.redundancy = redundancy
        
    def run(self):
        try:
            self.status_update.emit("Transmitting...")
            self.protocol.transmit_message(self.message, self.redundancy)
            self.status_update.emit("Transmission complete.")
        except Exception as e:
            self.status_update.emit(f"Error: {str(e)}")
        finally:
            self.finished.emit()


class MorseTransmitterApp(QMainWindow):
    """Main window for the Morse code transmitter application."""
    
    def __init__(self):
        super().__init__()
        
        # Initialize audio and protocol objects
        self.audio_generator = MorseAudioGenerator()
        self.protocol = TransmissionProtocol(self.audio_generator)
        
        # Configure the window
        self.setWindowTitle("Morse Code Transmitter")
        self.setGeometry(100, 100, 800, 600)
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Message input section
        message_group = QGroupBox("Message")
        message_layout = QVBoxLayout()
        
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.setMinimumHeight(100)
        message_layout.addWidget(self.message_input)
        
        message_group.setLayout(message_layout)
        main_layout.addWidget(message_group)
        
        # Morse code preview section
        morse_group = QGroupBox("Morse Code Preview")
        morse_layout = QVBoxLayout()
        
        self.morse_preview = QTextEdit()
        self.morse_preview.setReadOnly(True)
        self.morse_preview.setFont(QFont("Courier", 10))
        morse_layout.addWidget(self.morse_preview)
        
        self.message_input.textChanged.connect(self.update_morse_preview)
        
        morse_group.setLayout(morse_layout)
        main_layout.addWidget(morse_group)
        
        # Settings section
        settings_group = QGroupBox("Transmission Settings")
        settings_layout = QHBoxLayout()
        
        # WPM settings
        wpm_layout = QVBoxLayout()
        wpm_label = QLabel("Speed (WPM):")
        self.wpm_spinner = QSpinBox()
        self.wpm_spinner.setRange(10, 25)
        self.wpm_spinner.setValue(18)
        self.wpm_spinner.valueChanged.connect(self.update_settings)
        wpm_layout.addWidget(wpm_label)
        wpm_layout.addWidget(self.wpm_spinner)
        settings_layout.addLayout(wpm_layout)
        
        # Tone frequency settings
        freq_layout = QVBoxLayout()
        freq_label = QLabel("Tone Frequency (Hz):")
        self.freq_spinner = QSpinBox()
        self.freq_spinner.setRange(500, 1000)
        self.freq_spinner.setValue(750)
        self.freq_spinner.setSingleStep(10)
        self.freq_spinner.valueChanged.connect(self.update_settings)
        freq_layout.addWidget(freq_label)
        freq_layout.addWidget(self.freq_spinner)
        settings_layout.addLayout(freq_layout)
        
        # Volume settings
        volume_layout = QVBoxLayout()
        volume_label = QLabel("Volume:")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(1, 100)
        self.volume_slider.setValue(65)
        self.volume_slider.valueChanged.connect(self.update_settings)
        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_slider)
        settings_layout.addLayout(volume_layout)
        
        # Redundancy settings
        redundancy_layout = QVBoxLayout()
        redundancy_label = QLabel("Character Redundancy:")
        self.redundancy_spinner = QSpinBox()
        self.redundancy_spinner.setRange(1, 3)
        self.redundancy_spinner.setValue(1)
        redundancy_layout.addWidget(redundancy_label)
        redundancy_layout.addWidget(self.redundancy_spinner)
        settings_layout.addLayout(redundancy_layout)
        
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.test_button = QPushButton("Test Audio")
        self.test_button.clicked.connect(self.test_audio)
        button_layout.addWidget(self.test_button)
        
        self.transmit_button = QPushButton("Transmit Message")
        self.transmit_button.clicked.connect(self.transmit_message)
        self.transmit_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(self.transmit_button)
        
        main_layout.addLayout(button_layout)
        
        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        main_layout.addWidget(self.status_label)
        
        # Initialize worker thread variable
        self.worker = None
        
    def update_morse_preview(self):
        """Update the Morse code preview when message changes."""
        text = self.message_input.toPlainText()
        morse_code = MorseCode.encode(text)
        self.morse_preview.setText(morse_code)
        
    def update_settings(self):
        """Update audio generator and protocol settings."""
        wpm = self.wpm_spinner.value()
        freq = self.freq_spinner.value()
        volume = self.volume_slider.value() / 100.0
        
        self.audio_generator.tone_frequency = freq
        self.audio_generator.volume = volume
        self.protocol.wpm = wpm
        
    def test_audio(self):
        """Test the audio output with a short sequence."""
        test_sequence = [
            (True, 0.1),   # Short tone
            (False, 0.1),  # Short silence
            (True, 0.3),   # Long tone
            (False, 0.1),  # Short silence
            (True, 0.1)    # Short tone
        ]
        
        # Update status
        self.status_label.setText("Testing audio...")
        
        # Run in a separate thread to not block the UI
        def run_test():
            self.audio_generator.start_stream()
            self.audio_generator.play_timing_sequence(test_sequence)
            self.audio_generator.stop_stream()
            self.status_label.setText("Audio test complete")
        
        threading.Thread(target=run_test).start()
        
    def transmit_message(self):
        """Transmit the current message."""
        message = self.message_input.toPlainText()
        if not message:
            QMessageBox.warning(self, "Empty Message", 
                               "Please enter a message to transmit.")
            return
        
        # Disable the transmit button during transmission
        self.transmit_button.setEnabled(False)
        
        # Get the redundancy setting
        redundancy = self.redundancy_spinner.value()
        
        # Create and start the worker thread
        self.worker = TransmissionWorker(self.protocol, message, redundancy)
        self.worker.status_update.connect(self.update_status)
        self.worker.finished.connect(self.on_transmission_finished)
        self.worker.start()
    
    def update_status(self, status):
        """Update the status label."""
        self.status_label.setText(status)
    
    def on_transmission_finished(self):
        """Enable the transmit button when transmission is finished."""
        self.transmit_button.setEnabled(True)
    
    def closeEvent(self, event):
        """Clean up resources when the window is closed."""
        self.audio_generator.cleanup()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MorseTransmitterApp()
    window.show()
    sys.exit(app.exec_())