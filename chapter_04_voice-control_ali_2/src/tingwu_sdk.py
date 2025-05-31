#!/usr/bin/env python
# coding=utf-8

import os
import json
import datetime
import websocket
import threading
import time
from typing import Dict, List, Any, Optional, Callable

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from aliyunsdkcore.auth.credentials import AccessKeyCredential

from logger import logger


class TingwuSDK:
    """
    SDK for Alibaba Tongyi Tingwu real-time speech-to-text API
    """
    def __init__(self, access_key_id: str, access_key_secret: str, app_key: str):
        """
        Initialize the SDK with credentials
        
        Args:
            access_key_id: Alibaba Cloud Access Key ID
            access_key_secret: Alibaba Cloud Access Key Secret
            app_key: Tingwu App Key from console
        """
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.app_key = app_key
        
        self.acs_client = None
        self.task_id = None
        self.ws_url = None
        self.ws_client = None
        
        self.is_streaming = False
        self.is_connected = False
        
        # Callbacks
        self.on_transcription_result = None
        self.on_connection_open = None
        self.on_connection_close = None
        self.on_error = None
        
        logger.info("Tingwu SDK initialized")
        
    def _create_common_request(self, domain: str, version: str, protocol_type: str, method: str, uri: str) -> CommonRequest:
        """
        Create a common request for Alibaba Cloud API
        
        Args:
            domain: API domain
            version: API version
            protocol_type: Protocol type
            method: HTTP method
            uri: URI pattern
            
        Returns:
            A CommonRequest object
        """
        request = CommonRequest()
        request.set_accept_format('json')
        request.set_domain(domain)
        request.set_version(version)
        request.set_protocol_type(protocol_type)
        request.set_method(method)
        request.set_uri_pattern(uri)
        request.add_header('Content-Type', 'application/json')
        return request
    
    def _init_client(self) -> None:
        """Initialize the ACS client with credentials"""
        credentials = AccessKeyCredential(self.access_key_id, self.access_key_secret)
        self.acs_client = AcsClient(region_id='cn-beijing', credential=credentials)
        secrets = {"access_key_id": self.access_key_id, "access_key_secret": self.access_key_secret, "app_key": self.app_key}
        logger.info(f'ACS client initialized: {secrets}')

    def create_task(self, 
                    source_language: str = 'cn', 
                    format: str = 'pcm', 
                    sample_rate: int = 16000,
                    output_level: int = 2,
                    enable_translation: bool = False,
                    target_languages: List[str] = None) -> Dict:
        """
        Create a Tingwu real-time transcription task
        
        Args:
            source_language: Source language of audio (cn, en, multilingual, etc.)
            format: Audio format (pcm, opus, aac, etc.)
            sample_rate: Audio sample rate (16000 or 8000)
            output_level: 1 for final results only, 2 for interim results too
            enable_translation: Whether to enable translation
            target_languages: List of target languages for translation
            
        Returns:
            Dictionary containing task info including TaskId and MeetingJoinUrl
        """
        logger.info(f"Creating Tingwu task with source_language={source_language}, format={format}, sample_rate={sample_rate}")
        
        if self.acs_client is None:
            self._init_client()
        
        # Prepare request parameters
        body = {
            'AppKey': self.app_key,
            'Input': {
                'Format': format,
                'SampleRate': sample_rate,
                'SourceLanguage': source_language,
                'TaskKey': 'task' + datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
                'ProgressiveCallbacksEnabled': False,
            },
            'Parameters': {
                'Transcription': {
                    'OutputLevel': output_level
                }
            }
        }
        
        # Add translation parameters if enabled
        if enable_translation and target_languages:
            body['Parameters']['TranslationEnabled'] = enable_translation
            body['Parameters']['Translation'] = {
                'OutputLevel': output_level,
                'TargetLanguages': target_languages
            }
        
        # Create and send request
        request = self._create_common_request(
            domain='tingwu.cn-beijing.aliyuncs.com',
            version='2023-09-30',
            protocol_type='https',
            method='PUT',
            uri='/openapi/tingwu/v2/tasks'
        )
        request.add_query_param('type', 'realtime')

        
        request.set_content(json.dumps(body).encode('utf-8'))
        
        try:
            response = self.acs_client.do_action_with_exception(request)
            result = json.loads(response)
            
            if 'Code' in result and result['Code'] == '0' and 'Data' in result and 'TaskId' in result['Data'] and 'MeetingJoinUrl' in result['Data']:
                self.task_id = result['Data']['TaskId']
                self.ws_url = result['Data']['MeetingJoinUrl']
                logger.info(f"Task created successfully. TaskId: {self.task_id}")
                return result
            else:
                logger.error(f"Failed to create task. Response: {result}")
                raise Exception(f"Failed to create task: {result}")
                
        except Exception as e:
            logger.error(f"Error creating task: {str(e)}")
            logger.debug(f"Request details: domain='tingwu.cn-beijing.aliyuncs.com', version='2023-09-30', uri='/openapi/tingwu/v2/tasks'")
            raise
    
    def end_task(self) -> Dict:
        """
        End the Tingwu transcription task
        
        Returns:
            Dictionary containing response from the API
        """
        if not self.task_id:
            logger.error("No active task to end")
            raise Exception("No active task to end")
            
        logger.info(f"Ending task with ID: {self.task_id}")
        
        body = {
            'AppKey': self.app_key,
            'TaskId': self.task_id,
        }
        
        request = self._create_common_request(
            domain='tingwu.cn-beijing.aliyuncs.com',
            version='2023-09-30',
            protocol_type='https',
            method='PUT',
            uri='/openapi/tingwu/v2/tasks/end'
        )
        request.add_query_param('type', 'realtime')

        
        request.set_content(json.dumps(body).encode('utf-8'))
        
        try:
            response = self.acs_client.do_action_with_exception(request)
            result = json.loads(response)
            logger.info(f"Task ended successfully. Response: {result}")
            return result
        except Exception as e:
            logger.error(f"Error ending task: {str(e)}")
            raise
    
    def get_task_info(self) -> Dict:
        """
        Get information about the current Tingwu task
        
        Returns:
            Dictionary containing task information
        """
        if not self.task_id:
            logger.error("No task ID available")
            raise Exception("No task ID available")
            
        logger.info(f"Getting info for task with ID: {self.task_id}")
        
        body = {
            'AppKey': self.app_key,
            'TaskId': self.task_id,
        }
        
        request = self._create_common_request(
            domain='tingwu.cn-beijing.aliyuncs.com',
            version='2023-09-30',
            protocol_type='https',
            method='PUT',
            uri='/openapi/tingwu/v2/tasks/info'
        )
        request.add_query_param('type', 'realtime')
        
        request.set_content(json.dumps(body).encode('utf-8'))
        
        try:
            response = self.acs_client.do_action_with_exception(request)
            result = json.loads(response)
            logger.info(f"Task info retrieved successfully")
            return result
        except Exception as e:
            logger.error(f"Error getting task info: {str(e)}")
            raise
    
    def _on_ws_open(self, ws):
        """WebSocket open callback"""
        logger.info("WebSocket connection established")
        self.is_connected = True
        
        # Send initial message for protocol handshake
        try:
            # First try to send a WebSocket protocol handshake message
            # Construct a simple handshake message that follows the expected format
            # This is crucial for establishing the audio stream connection
            handshake_msg = {
                "app_key": self.app_key,
                "message_id": f"msg_{int(time.time()*1000)}",
                "payload_type": "handshake",
                "task_id": self.task_id,
                "payload": {
                    "version": "2.0",
                    "format": "pcm",
                    "sample_rate": 16000
                }
            }
            ws.send(json.dumps(handshake_msg))
            logger.info("Sent JSON handshake message")
            
            # Also send an empty binary frame to confirm binary protocol
            ws.send("".encode(), websocket.ABNF.OPCODE_BINARY)
            logger.debug("Sent binary handshake message")
            
        except Exception as e:
            logger.error(f"Error during WebSocket handshake: {str(e)}")
        
        if self.on_connection_open:
            self.on_connection_open()
    
    def _on_ws_message(self, ws, message):
        """WebSocket message callback"""
        try:
            # Log raw message first in case parsing fails
            logger.debug(f"Received raw message: {message[:100]}{'...' if len(message) > 100 else ''}")
            
            # Parse JSON response
            result = json.loads(message)
            
            # Log complete parsed data at debug level
            logger.debug(f"Received transcription data: {result}")
            
            # Check for errors or status messages in the response
            if 'Code' in result and result['Code'] != '0':
                logger.warning(f"Server returned non-zero code: {result['Code']}, Message: {result.get('Message', 'Unknown error')}")
            
            # Pass to callback if set
            if self.on_transcription_result:
                self.on_transcription_result(result)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {str(e)}. Raw message: {message[:100]}")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
    
    def _on_ws_error(self, ws, error):
        """WebSocket error callback"""
        # Provide detailed diagnostics about the error
        logger.error(f"WebSocket error: {str(error)}")
        logger.error(f"WebSocket URL: {self.ws_url}")
        
        # Extract more details from the error if possible
        error_type = type(error).__name__
        error_dict = {
            "error_type": error_type,
            "error_message": str(error),
            "task_id": self.task_id,
            "is_connected": self.is_connected,
            "is_streaming": self.is_streaming
        }
        logger.error(f"WebSocket error details: {error_dict}")
        
        if self.on_error:
            self.on_error(error)
    
    def _on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket close callback"""
        # Provide detailed diagnostics about the connection closure
        logger.info(f"WebSocket connection closed: Code={close_status_code}, Message={close_msg}")
        
        # Map common WebSocket close codes to human-readable reasons
        close_reasons = {
            1000: "Normal closure",
            1001: "Going away",
            1002: "Protocol error",
            1003: "Unsupported data",
            1005: "No status received",
            1006: "Abnormal closure",
            1007: "Invalid frame payload data",
            1008: "Policy violation",
            1009: "Message too big",
            1010: "Mandatory extension",
            1011: "Internal server error",
            1012: "Service restart",
            1013: "Try again later",
            1015: "TLS handshake"
        }
        
        if close_status_code is not None:
            reason = close_reasons.get(close_status_code, "Unknown reason")
            logger.info(f"WebSocket close reason: {reason}")
            
            # Suggest action based on the close code
            if close_status_code == 1006:
                logger.warning("Abnormal closure suggests connection was terminated unexpectedly. Check network conditions.")
            elif close_status_code == 1011:
                logger.warning("Server encountered an error. You might want to retry after a delay.")
        
        self.is_connected = False
        self.is_streaming = False
        
        if self.on_connection_close:
            self.on_connection_close()
    
    def start_streaming(self) -> None:
        """
        Start WebSocket connection to Tingwu API for streaming audio
        """
        if not self.ws_url:
            logger.error("No WebSocket URL available. Create a task first.")
            raise Exception("No WebSocket URL available. Create a task first.")
        
        logger.info(f"Starting WebSocket connection to: {self.ws_url}")
        
        # Enable trace for debugging (uncomment if needed)
        # websocket.enableTrace(True)
        
        # Initialize WebSocket connection with additional options
        self.ws_client = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close,
            header={
                "Origin": "https://tingwu.aliyun.com",
                "User-Agent": "Mozilla/5.0 Tingwu SDK Python"
            }
        )
        
        # Start WebSocket connection in a separate thread with keep_running=True
        websocket_options = {
            "ping_interval": 30,  # Send ping every 30 seconds to keep connection alive
            "ping_timeout": 10,   # Wait 10 seconds for pong before considering connection dead
            "skip_utf8_validation": True  # Skip UTF-8 validation for better performance with binary data
        }
        
        self.ws_thread = threading.Thread(
            target=lambda: self.ws_client.run_forever(**websocket_options)
        )
        self.ws_thread.daemon = True
        self.ws_thread.start()
        
        # Wait for connection to establish
        timeout = 15  # Increased timeout for connection
        start_time = time.time()
        while not self.is_connected and time.time() - start_time < timeout:
            time.sleep(0.1)
            
        if not self.is_connected:
            logger.error(f"WebSocket connection failed to establish within {timeout} seconds")
            raise Exception(f"WebSocket connection failed to establish within {timeout} seconds")
            
        self.is_streaming = True
        logger.info("WebSocket streaming started")
    
    def send_audio_data(self, audio_data: bytes) -> None:
        """
        Send audio data to Tingwu API via WebSocket
        
        Args:
            audio_data: Audio data in bytes (should match the format specified in create_task)
        """
        if not self.is_connected or not self.is_streaming:
            logger.error("WebSocket not connected")
            return
            
        try:
            self.ws_client.send(audio_data, websocket.ABNF.OPCODE_BINARY)
        except Exception as e:
            logger.error(f"Error sending audio data: {str(e)}")
            if self.on_error:
                self.on_error(e)
    
    def stop_streaming(self) -> None:
        """Stop WebSocket streaming"""
        if self.ws_client and self.is_connected:
            logger.info("Stopping WebSocket streaming")
            self.is_streaming = False
            self.ws_client.close()
            self.ws_thread.join(timeout=5)
            logger.info("WebSocket streaming stopped")
    
    def set_callbacks(self, 
                     on_transcription_result: Optional[Callable] = None,
                     on_connection_open: Optional[Callable] = None,
                     on_connection_close: Optional[Callable] = None,
                     on_error: Optional[Callable] = None) -> None:
        """
        Set callbacks for different events
        
        Args:
            on_transcription_result: Callback for transcription results
            on_connection_open: Callback when WebSocket connection opens
            on_connection_close: Callback when WebSocket connection closes
            on_error: Callback for errors
        """
        self.on_transcription_result = on_transcription_result
        self.on_connection_open = on_connection_open
        self.on_connection_close = on_connection_close
        self.on_error = on_error
        logger.debug("Callbacks set")
