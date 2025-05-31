#!/usr/bin/env python
# coding=utf-8

import os
import time
import argparse
import json
from dotenv import load_dotenv

from tingwu_sdk import TingwuSDK
from audio_capture import AudioCapture
from logger import logger

load_dotenv()

def on_transcription_result(result):
    """
    Callback for transcription results
    
    Args:
        result: The transcription result from Tingwu API
    """
    # Process different result types
    if 'TranscriptionResult' in result:
        sentence = result['TranscriptionResult'].get('SentenceText', '')
        is_sentence_end = result['TranscriptionResult'].get('SentenceEnd', False)
        
        if is_sentence_end:
            print(f"Final: {sentence}")
        else:
            print(f"Interim: {sentence}", end="\r")
    
    # Handle translation results if present
    if 'TranslationResult' in result:
        for lang, translation in result['TranslationResult'].items():
            sentence = translation.get('SentenceText', '')
            is_sentence_end = translation.get('SentenceEnd', False)
            
            if is_sentence_end:
                print(f"Translation ({lang}): {sentence}")

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
            on_connection_open=lambda: print("WebSocket connection opened"),
            on_connection_close=lambda: print("WebSocket connection closed"),
            on_error=lambda error: print(f"Error: {error}")
        )
        
        # Start WebSocket connection
        sdk.start_streaming()
        
        # Initialize audio capture
        audio = AudioCapture(rate=args.sample_rate)
        
        # Set up callback for audio data
        audio.set_audio_callback(sdk.send_audio_data)
        
        # Start recording
        print("\nStarting microphone recording...")
        print(f"Recording for {args.duration} seconds. Speak now...")
        audio.start()
        
        # Record for specified duration
        time.sleep(args.duration)
        
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
