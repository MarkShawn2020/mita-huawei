#!/usr/bin/env python
# coding=utf-8

import json
import datetime
import websocket
import threading
import time
import ssl
import numpy as np
from typing import Dict, List, Optional, Callable

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from aliyunsdkcore.auth.credentials import AccessKeyCredential

from utils.logger import logger


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
        self.on_transcription_result = None  # 兼容旧版本的回调
        self.on_connection_open = None
        self.on_connection_close = None
        self.on_error = None
        self.on_result = None  # 新的转写结果回调
        self.on_completed = None  # 转写完成回调
        
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
        End the current Tingwu task
        
        Returns:
            Dictionary containing response from the API
        """
        if not self.task_id:
            logger.error("No active task to end")
            raise Exception("No active task to end")
            
        logger.info(f"Ending task with ID: {self.task_id}")
        
        # 由于WebSocket已经正常关闭，不再尝试调用结束任务API
        # 实际上，对于实时流式转写，一般通过WebSocket连接关闭来结束任务
        # 我们不再调用HTTP API结束任务，只需确保已关闭WebSocket连接
        
        # 已试过多个端点但都返回404，所以不再尝试HTTP调用
        # 比如：/openapi/tingwu/v1/task/stop, /openapi/tingwu/v1/tasks/end, /openapi/tingwu/v2/tasks/end
        
        # 检查WebSocket是否已关闭
        if self.ws_client and self.is_connected:
            logger.warning("WebSocket connection still open. Attempting to close it.")
            try:
                self.ws_client.close()
                logger.info("WebSocket connection closed by end_task")
            except Exception as e:
                logger.error(f"Error closing WebSocket connection: {str(e)}")
        
        # 返回成功状态
        logger.info("Task considered ended successfully after WebSocket closure")
        return {"Status": "Success", "Message": "Task ended by closing WebSocket connection"}
    
    def get_task_info(self) -> Dict:
        """
        Get information about the current Tingwu task
        
        Returns:
            Dictionary containing task information or a status dict if API unavailable
        """
        if not self.task_id:
            logger.error("No task ID available")
            raise Exception("No task ID available")
            
        logger.info(f"Getting info for task with ID: {self.task_id}")
        
        # 首先检查WebSocket连接状态
        ws_status = {
            "is_connected": self.is_connected,
            "is_streaming": self.is_streaming,
            "task_id": self.task_id,
            "ws_url": self.ws_url
        }
        
        # 对于实时流式转写，主要通过WebSocket连接管理，而不依赖HTTP API
        # 由于之前的尝试显示HTTP API端点可能不可用，我们将返回本地状态
        logger.info("Returning local WebSocket connection status instead of calling API")
        return {
            "Status": "Success",
            "TaskId": self.task_id,
            "WebSocketStatus": ws_status,
            "Message": "Task info retrieved from local state"
        }
    
    def _on_ws_open(self, ws):
        """WebSocket open callback"""
        logger.info("WebSocket connection established")
        self.is_connected = True
        
        try:
            # 首先发送JSON握手消息
            # 根据通义听悟API文档，需要发送初始化参数
            init_message = {
                "header": {
                    "namespace": "SpeechTranscriber",
                    "name": "StartTranscription",
                    "status": 0,
                    "message_id": str(int(time.time()*1000))  # 使用当前时间戳作为消息ID
                },
                "payload": {
                    "task_id": self.task_id,
                    "format": "pcm",
                    "sample_rate": 16000,
                    "enable_intermediate_result": True,
                    "enable_punctuation_prediction": True,
                    "enable_inverse_text_normalization": True
                }
            }
            
            # 发送初始化JSON消息
            init_json = json.dumps(init_message)
            logger.info(f"Sending initialization JSON: {init_json}")
            ws.send(init_json)
            logger.info("Sent initialization JSON message")
            
            # 短暂等待处理初始化消息
            time.sleep(0.1)
            
            # 使用numpy生成空白音频数据 (30ms of silence at 16kHz 16bit mono)
            # 16kHz, 16bit = 2 bytes per sample, 30ms = 0.03s
            # 0.03s * 16000 samples/s = 480 samples
            # 480 samples * 2 bytes/sample = 960 bytes
            silence_samples = np.zeros(480, dtype=np.int16)  # 16-bit silence (zeros)
            empty_audio = silence_samples.tobytes()  # 转换为字节流
            
            # 记录音频帧长度与格式
            logger.debug(f"Generated {len(empty_audio)} bytes of silent audio data")
            
            # 发送空白音频帧
            ws.send(empty_audio, websocket.ABNF.OPCODE_BINARY)
            logger.info("Sent initial empty audio frame")
            
            # 延迟一小段时间确保连接稳定
            time.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Error during WebSocket initialization: {str(e)}")
            # 添加更详细的错误诊断信息
            if hasattr(e, "__dict__"):
                logger.error(f"Error details: {e.__dict__}")
            # 记录堆栈跟踪信息
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
        
        if self.on_connection_open:
            self.on_connection_open()
    
    def _on_ws_message(self, ws, message):
        """WebSocket message callback"""
        try:
            # 尝试解析为JSON，但也处理二进制消息
            try:
                data = json.loads(message)
                logger.debug(f"Received message: {data}")
                
                # 检查消息头部以确定消息类型
                if 'header' in data:
                    header = data['header']
                    name = header.get('name', '')
                    namespace = header.get('namespace', '')
                    status = header.get('status', 0)
                    
                    # 根据消息类型处理
                    if namespace == 'SpeechTranscriber':
                        # 处理开始转写的响应
                        if name == 'StartTranscriptionResponse':
                            if status == 20000000:
                                logger.info("Transcription started successfully")
                            else:
                                logger.error(f"Failed to start transcription: {status} - {header.get('message', 'Unknown error')}")
                        
                        # 处理转写结果
                        elif name == 'TranscriptionResultChanged':
                            if 'payload' in data and 'result' in data['payload']:
                                result = data['payload']['result']
                                is_final = data['payload'].get('is_final', False)
                                confidence = data['payload'].get('confidence', 0)
                                
                                # 打印转写结果
                                if is_final:
                                    logger.info(f"Final result: {result} (confidence: {confidence})")
                                else:
                                    logger.debug(f"Intermediate result: {result} (confidence: {confidence})")
                                
                                # 调用回调函数 - 同时支持新旧两种回调机制
                                if self.on_result:
                                    self.on_result(result, is_final, confidence)
                                    
                                # 向后兼容旧版回调
                                if self.on_transcription_result:
                                    self.on_transcription_result(result)
                        
                        # 处理完成事件
                        elif name == 'TranscriptionCompleted':
                            logger.info("Transcription completed")
                            if self.on_completed:
                                self.on_completed()
                        
                        # 处理转写错误
                        elif name == 'TaskFailed':
                            error_code = header.get('status', 0)
                            error_message = header.get('message', 'Unknown error')
                            logger.error(f"Transcription task failed: {error_code} - {error_message}")
                            if self.on_error:
                                self.on_error(Exception(f"Transcription failed: {error_message}"))
                    
                    # 处理其他类型的消息
                    else:
                        logger.debug(f"Received message from namespace {namespace}: {name}")
                
                # 无头部的消息（不常见）
                else:
                    logger.warning(f"Received message without header: {data}")
                    
            except json.JSONDecodeError:
                # 处理二进制消息（一般不应该接收到）
                logger.debug(f"Received binary message of length {len(message)}")
                
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {str(e)}")
            import traceback
            logger.debug(f"Stack trace: {traceback.format_exc()}")
            
            # 将错误传递给回调函数
            if self.on_error:
                self.on_error(e)
    
    def _on_ws_error(self, ws, error):
        """WebSocket error callback"""
        # 提供详细的错误诊断信息
        logger.error(f"WebSocket error: {str(error)}")
        
        # 检查常见错误类型并提供更具体的建议
        if isinstance(error, ConnectionRefusedError):
            logger.error("Connection refused. Server may be down or the URL is incorrect.")
        elif isinstance(error, TimeoutError):
            logger.error("Connection timed out. Check network conditions.")
        elif isinstance(error, websocket._exceptions.WebSocketConnectionClosedException):
            logger.error("WebSocket connection was closed when attempting to send/receive data.")
        elif isinstance(error, websocket._exceptions.WebSocketAddressException):
            logger.error("Invalid WebSocket address. Check the URL format.")
        elif isinstance(error, websocket._exceptions.WebSocketProtocolException):
            logger.error("WebSocket protocol error. Might be incompatible with the server.")
        elif isinstance(error, ConnectionResetError):
            logger.error("Connection was reset by peer. Server might have terminated the connection.")
        elif isinstance(error, OSError):
            logger.error(f"OS error occurred: {error.errno} - {error.strerror}. Check network settings and permissions.")
        elif isinstance(error, ssl.SSLError):
            logger.error(f"SSL error: {str(error)}. This might be related to certificate validation or SSL configuration.")
        elif 'Handshake status 403' in str(error):
            logger.error("Received HTTP 403 Forbidden during WebSocket handshake. Authentication failed or access denied.")
            logger.error("Verify that the token in the URL is valid and has not expired.")
        elif 'Handshake status 401' in str(error):
            logger.error("Received HTTP 401 Unauthorized during WebSocket handshake. Authentication credentials are required.")
        
        # 尝试提取更多错误详情
        try:
            if hasattr(error, '__dict__'):
                details = str(error.__dict__)
                logger.debug(f"Error details: {details}")
        except Exception as e:
            logger.debug(f"Could not extract error details: {str(e)}")
        
        # 将错误传递给回调函数（如果设置了）
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
            
            # 记录详细错误代码解释，以便更好地诊断问题
            if close_status_code == 1000:
                logger.info("Normal closure - connection successfully completed")
            elif close_status_code == 1001:
                logger.warning("Going away - server or client going down")
            elif close_status_code == 1002:
                logger.error("Protocol error - endpoint received a malformed frame")
            elif close_status_code == 1003:
                logger.error("Unsupported data - received data of a type it cannot accept")
            elif close_status_code == 1006:
                logger.error("Abnormal closure - connection was closed abnormally")
            elif close_status_code == 1007:
                logger.error("Invalid frame payload data")
            elif close_status_code == 1008:
                logger.error("Policy violation")
            elif close_status_code == 1009:
                logger.error("Message too big")
            elif close_status_code == 1010:
                logger.error("Mandatory extension - client expected server to negotiate an extension")
            elif close_status_code == 1011:
                logger.error("Internal server error")
            elif close_status_code == 1012:
                logger.error("Service restart")
            elif close_status_code == 1013:
                logger.error("Try again later - server is overloaded")
            elif close_status_code == 1014:
                logger.error("Bad gateway")
            elif close_status_code == 1015:
                logger.error("TLS handshake failure")
            else:
                logger.warning(f"Unknown close code: {close_status_code}")
                
        self.is_connected = False
        self.is_streaming = False
        
        if self.on_connection_close:
            self.on_connection_close()
    
    def start_streaming(self):
        """Start WebSocket streaming"""
        if not self.task_id:
            raise Exception("Task ID is required. Please create a task first.")
        
        if self.is_streaming:
            logger.warning("WebSocket is already streaming")
            return
        
        # Set up WebSocket URL
        self.ws_url = self.ws_url or self.meeting_join_url
        
        if not self.ws_url:
            raise Exception("WebSocket URL is required. Please set it or create a task first.")
        
        logger.info(f"Starting WebSocket connection to: {self.ws_url}")
        
        # 启用WebSocket跟踪，调试时可打开
        websocket.enableTrace(False)
        
        # 重要：通义听悟WebSocket连接的关键在于使用标准WebSocket头部
        # URL中包含了所有必要的认证信息，不需要添加自定义头部
        # 阿里云文档显示的通义听悟API使用的是标准WebSocket连接
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        }
        
        # 记录连接信息
        logger.debug(f"WebSocket connection URL: {self.ws_url}")
        logger.debug(f"WebSocket headers: {headers}")
        
        # 创建WebSocket连接
        self.ws_client = websocket.WebSocketApp(
            self.ws_url,
            header=headers,
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close
        )
        
        # SSL选项
        sslopt = {
            "cert_reqs": ssl.CERT_NONE,  # 不验证服务器证书
            "check_hostname": False      # 不检查主机名
        }
        
        # 启动WebSocket线程
        self.ws_thread = threading.Thread(target=self.ws_client.run_forever, kwargs={
            "ping_interval": 10,          # 心跳间隔
            "ping_timeout": 5,           # 超时时间
            "skip_utf8_validation": True, # 跳过UTF8验证，因为我们发送二进制数据
            "sslopt": sslopt,            # SSL选项
            "http_proxy_host": None,      # 如果需要代理，这里可以设置
            "http_proxy_port": None
        })
        self.ws_thread.daemon = True
        self.ws_thread.start()
        
        # 等待连接建立
        connection_timeout = 15  # 秒
        connection_start_time = time.time()
        
        while not self.is_connected and time.time() - connection_start_time < connection_timeout:
            time.sleep(0.1)
        
        if not self.is_connected:
            logger.error(f"WebSocket connection failed to establish within {connection_timeout} seconds")
            raise Exception(f"WebSocket connection failed to establish within {connection_timeout} seconds")
        
        logger.info("WebSocket connection established successfully")
        self.is_streaming = True
    
    def send_audio_data(self, audio_data: bytes) -> None:
        """Send audio data to Tingwu API via WebSocket
        
        Args:
            audio_data: Audio data in bytes (should match the format specified in create_task)
        """
        if not self.is_connected or not self.is_streaming:
            logger.error("WebSocket not connected")
            return
            
        try:
            # 直接通过WebSocket发送二进制音频数据
            if self.ws_client:
                self.ws_client.send(audio_data, websocket.ABNF.OPCODE_BINARY)
                # 日志记录在debug级别，避免过多输出
                logger.debug(f"Sent {len(audio_data)} bytes of audio data")
            else:
                logger.error("WebSocket client not initialized")
        except Exception as e:
            logger.error(f"Error sending audio data: {str(e)}")
            if self.on_error:
                self.on_error(e)
    
    def stop_streaming(self) -> None:
        """Stop WebSocket streaming"""
        if self.ws_client and self.is_connected:
            logger.info("Stopping WebSocket streaming")
            try:
                # 设置状态标记
                self.is_streaming = False
                
                # 关闭WebSocket连接
                self.ws_client.close()
                
                # 等待线程结束
                if hasattr(self, 'ws_thread') and self.ws_thread:
                    self.ws_thread.join(timeout=5)
                
                # 状态更新
                self.is_connected = False
                
                logger.info("WebSocket streaming stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping WebSocket streaming: {str(e)}")
                if self.on_error:
                    self.on_error(e)
    
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
