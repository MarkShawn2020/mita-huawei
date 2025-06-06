#!/usr/bin/env python
# coding=utf-8

import os
import time
import argparse
from dotenv import load_dotenv

from core.tingwu_sdk.ws import TingwuSDK
from core.audio_capture import AudioCapture
from utils.logger import logger

load_dotenv()

def on_transcription_result(result: str):
    """
    Callback for transcription results
    
    Args:
        result: The transcription result from Tingwu API
    """
    # Log full result for debugging
    logger.info(f"Full result: {result}")

def main():
    """Main function to demonstrate real-time speech-to-text using Tingwu SDK"""
    parser = argparse.ArgumentParser(description='Alibaba Tongyi Tingwu real-time speech-to-text demo')
    parser.add_argument('--access-key-id', help='Alibaba Cloud Access Key ID')
    parser.add_argument('--access-key-secret', help='Alibaba Cloud Access Key Secret')
    parser.add_argument('--app-key', help='Tingwu App Key')
    parser.add_argument('--language', default='cn', help='Source language (cn, en, multilingual)')
    parser.add_argument('--enable-translation', action='store_true', help='Enable translation')
    parser.add_argument('--target-language', default='en', help='Target language for translation')
    parser.add_argument('--sample-rate', type=int, default=16000, help='Audio sample rate (8000 or 16000)')

    # todo: 可以升级为多长时间没有声音就停止程序
    parser.add_argument('--duration', type=int, default=30, help='Recording duration in seconds')
    args = parser.parse_args()

    # Get credentials from arguments or environment variables
    access_key_id = args.access_key_id or os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID')
    access_key_secret = args.access_key_secret or os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
    app_key = args.app_key or os.environ.get('TINGWU_APP_KEY')
    
    logger.info("Credentials loaded" + (" successfully" if all([access_key_id, access_key_secret, app_key]) else " with missing values"))
    
    if not access_key_id or not access_key_secret or not app_key:
        print("Error: Missing credentials. Please provide them as arguments or environment variables.")
        return
    
    # Initialize Tingwu SDK
    sdk = TingwuSDK(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        app_key=app_key
    )
    
    # Set up target languages for translation
    target_languages = None
    if args.enable_translation:
        target_languages = [args.target_language]
    
    try:
        # Create task
        task_info = sdk.create_task(
            source_language=args.language,
            format='pcm',
            sample_rate=args.sample_rate,
            output_level=2,  # Get interim results
            enable_translation=args.enable_translation,
            target_languages=target_languages
        )
        
        print(f"Task created with ID: {task_info['Data']['TaskId']}")
        print(f"WebSocket URL: {task_info['Data']['MeetingJoinUrl']}")
        
        # Set up callback for transcription results
        sdk.set_callbacks(
            on_transcription_result=on_transcription_result,
            on_connection_open=lambda: print("\nWebSocket connection opened and ready to stream audio"),
            on_connection_close=lambda: print("\nWebSocket connection closed - will try to reconnect if still recording"),
            on_error=lambda error: print(f"\nWebSocket error: {error}")
        )
        
        # Start WebSocket connection
        sdk.start_streaming()
        
        # Initialize audio capture
        audio = AudioCapture(rate=args.sample_rate)
        
        # Set up callback for audio data
        audio.set_audio_callback(sdk.send_audio_data)
        
        # Start recording with connection check
        print("\nStarting microphone recording...")
        print(f"Recording for {args.duration} seconds. Speak now...")
        audio.start()
        
        # Monitor connection status during recording
        start_time = time.time()
        connection_check_interval = 2  # Check connection every 2 seconds
        next_check_time = start_time + connection_check_interval
        
        while time.time() - start_time < args.duration:
            if time.time() >= next_check_time:
                if not sdk.is_connected:
                    print("\nWebSocket connection lost, attempting to reconnect...")
                    try:
                        # Try to restart streaming
                        sdk.stop_streaming()
                        time.sleep(1)
                        sdk.start_streaming()
                        print("Reconnected successfully")
                    except Exception as e:
                        print(f"\nFailed to reconnect: {e}")
                        break
                next_check_time = time.time() + connection_check_interval
            time.sleep(0.1)  # Small sleep to prevent CPU overuse
        
        # Stop recording
        print("\nStopping recording...")
        audio.stop()
        
        # Stop streaming
        sdk.stop_streaming()
        
        # End task
        print("Ending task...")
        sdk.end_task()
        
        # Get final task info
        task_info = sdk.get_task_info()
        print(f"Task status: {task_info.get('Status', 'Unknown')}")
        
    except Exception as e:
        logger.error(f"Error in demo: {str(e)}")
        print(f"Error: {str(e)}")
    
if __name__ == "__main__":
    main()
