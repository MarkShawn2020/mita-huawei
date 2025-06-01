#!/usr/bin/env python
# coding=utf-8

import pyaudio
import threading
import time
from typing import Callable

from utils.logger import logger

class AudioCapture:
    """
    Audio capture module for recording microphone input
    """
    def __init__(self, 
                 format: int = pyaudio.paInt16,
                 channels: int = 1,
                 rate: int = 16000,
                 chunk_size: int = 1024):
        """
        Initialize audio capture with the specified parameters
        
        Args:
            format: Audio format (default: 16-bit int)
            channels: Number of audio channels (default: 1 - mono)
            rate: Sampling rate in Hz (default: 16000)
            chunk_size: Number of frames per buffer (default: 1024)
        """
        self.format = format
        self.channels = channels
        self.rate = rate
        self.chunk_size = chunk_size
        
        self.p = None
        self.stream = None
        self.is_recording = False
        self.recording_thread = None
        
        # Callback for audio data
        self.on_audio_data = None
        
        logger.info(f"AudioCapture initialized with rate={rate}Hz, channels={channels}, format={format}, chunk_size={chunk_size}")
    
    def set_audio_callback(self, callback: Callable[[bytes], None]) -> None:
        """
        Set callback for audio data
        
        Args:
            callback: Function to call with audio data
        """
        self.on_audio_data = callback
        logger.debug("Audio callback set")
    
    def _audio_callback(self, in_data, frame_count, time_info, status) -> tuple:
        """
        Callback for PyAudio stream to process audio data
        
        Args:
            in_data: Input audio data
            frame_count: Number of frames
            time_info: Time information
            status: Status flag
            
        Returns:
            Tuple of (None, flag) where flag indicates stream should continue
        """
        if self.is_recording and self.on_audio_data:
            self.on_audio_data(in_data)
        return (None, pyaudio.paContinue)
    
    def _recording_thread_func(self) -> None:
        """Recording thread function that reads from the audio stream"""
        logger.info("Recording thread started")
        
        try:
            while self.is_recording:
                if self.stream:
                    data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    if self.is_recording and self.on_audio_data:
                        self.on_audio_data(data)
                time.sleep(0.001)  # Small sleep to prevent CPU overuse
        except Exception as e:
            logger.error(f"Error in recording thread: {str(e)}")
            self.stop()
            
        logger.info("Recording thread stopped")
    
    def start(self) -> None:
        """Start audio capture from microphone"""
        if self.is_recording:
            logger.warning("Already recording")
            return
            
        logger.info("Starting audio capture")
        
        try:
            self.p = pyaudio.PyAudio()
            
            # Get device info
            info = self.p.get_default_input_device_info()
            logger.info(f"Using audio input device: {info['name']}")
            
            # Open stream
            self.stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk_size,
            )
            
            self.is_recording = True
            
            # Start recording thread
            self.recording_thread = threading.Thread(target=self._recording_thread_func)
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
            logger.info("Audio capture started")
            
        except Exception as e:
            logger.error(f"Error starting audio capture: {str(e)}")
            self.stop()
            raise
    
    def stop(self) -> None:
        """Stop audio capture"""
        if not self.is_recording:
            return
            
        logger.info("Stopping audio capture")
        self.is_recording = False
        
        # Stop thread
        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)
            self.recording_thread = None
        
        # Close stream
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            
        # Terminate PyAudio
        if self.p:
            self.p.terminate()
            self.p = None
            
        logger.info("Audio capture stopped")
