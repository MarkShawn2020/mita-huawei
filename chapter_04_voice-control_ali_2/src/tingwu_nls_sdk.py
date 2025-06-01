#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
使用阿里云官方SDK实现的通义听悟客户端
基于 alibaba-nls-python-sdk 中的 NlsSpeechTranscriber 类
"""

import os
import time
import json
import datetime
import traceback
import urllib.parse
import threading
import uuid
from typing import Dict, Optional, Callable, List, Any

import nls
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest

from logger import Logger

logger = Logger().logger

class TingwuNlsSDK:
    """通义听悟SDK基于阿里云官方NLS SDK的实现"""
    
    def __init__(self, access_key_id: str, access_key_secret: str, app_key: str):
        """
        初始化通义听悟SDK
        
        Args:
            access_key_id: 阿里云访问密钥ID
            access_key_secret: 阿里云访问密钥密钥
            app_key: 通义听悟应用密钥
        """
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.app_key = app_key
        
        # 初始化ACS客户端
        self.acs_client = AcsClient(
            ak=access_key_id,
            secret=access_key_secret,
            region_id='cn-beijing'
        )
        logger.info(f"ACS client initialized: {{'access_key_id': '{access_key_id}', 'access_key_secret': '{access_key_secret[:5]}...', 'app_key': '{app_key}'}}")
        
        # 任务相关属性
        self.task_id = None
        self.ws_url = None
        
        # 转写器实例
        self.transcriber = None
        
        # 音频捕获线程
        self.is_capturing = False
        self.capture_thread = None
        
        # 回调函数
        self.on_result = None
        self.on_sentence_begin = None
        self.on_sentence_end = None 
        self.on_completed = None
        self.on_error = None
        self.on_connection_open = None
        self.on_connection_close = None
        
        # 状态标志
        self.is_connected = False
        self.is_streaming = False
        
        logger.info("Tingwu NLS SDK initialized")
    
    def set_callbacks(self, 
                      on_result: Optional[Callable[[str, bool, float], None]] = None,
                      on_sentence_begin: Optional[Callable[[Dict], None]] = None,
                      on_sentence_end: Optional[Callable[[Dict], None]] = None,
                      on_completed: Optional[Callable[[Dict], None]] = None,
                      on_error: Optional[Callable[[str], None]] = None,
                      on_connection_open: Optional[Callable[[], None]] = None,
                      on_connection_close: Optional[Callable[[], None]] = None):
        """
        设置回调函数
        
        Args:
            on_result: 转写结果回调
            on_sentence_begin: 句子开始回调
            on_sentence_end: 句子结束回调
            on_completed: 转写完成回调
            on_error: 错误回调
            on_connection_open: 连接打开回调
            on_connection_close: 连接关闭回调
        """
        self.on_result = on_result
        self.on_sentence_begin = on_sentence_begin
        self.on_sentence_end = on_sentence_end
        self.on_completed = on_completed
        self.on_error = on_error
        self.on_connection_open = on_connection_open
        self.on_connection_close = on_connection_close
        logger.debug("Callbacks set")
    
    def create_task(self, source_language: str = "cn", format: str = "pcm", sample_rate: int = 16000, output_level: int = 2, enable_translation: bool = False, target_languages: List[str] = None) -> Dict:
        """
        创建通义听悟任务
        
        Args:
            source_language: 源语言，默认为中文
            format: 音频格式，默认为PCM
            sample_rate: 采样率，默认为16000Hz
            output_level: 1 表示仅最终结果，2 表示包含中间结果
            enable_translation: 是否启用翻译
            target_languages: 翻译目标语言列表
            
        Returns:
            包含任务ID和WebSocket URL的字典
        """
        logger.info(f"Creating Tingwu task with source_language={source_language}, format={format}, sample_rate={sample_rate}")
        
        # 创建CommonRequest对象
        request = self._create_common_request(
            domain='tingwu.cn-beijing.aliyuncs.com',
            version='2023-09-30',
            protocol_type='https',
            method='PUT',  # 使用PUT而不是POST
            uri='/openapi/tingwu/v2/tasks'  # 使用v2 API
        )
        
        # 添加查询参数
        request.add_query_param('type', 'realtime')
        
        # 设置请求体 - 与原始实现保持一致的结构
        body = {
            'AppKey': self.app_key,
            'Input': {
                'Format': format,
                'SampleRate': sample_rate,
                'SourceLanguage': source_language,
                'TaskKey': 'task' + time.strftime('%Y%m%d%H%M%S'),
                'ProgressiveCallbacksEnabled': False,
            },
            'Parameters': {
                'Transcription': {
                    'OutputLevel': output_level
                }
            }
        }
        
        # 添加翻译参数（如果启用）
        if enable_translation and target_languages:
            body['Parameters']['TranslationEnabled'] = enable_translation
            body['Parameters']['Translation'] = {
                'OutputLevel': output_level,
                'TargetLanguages': target_languages
            }
        
        request.set_content(json.dumps(body).encode('utf-8'))
        
        try:
            response = self.acs_client.do_action_with_exception(request)
            result = json.loads(response)
            logger.info(f"create task result: {result}")
            
            # 验证响应格式
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
    
    def start_streaming(self, enable_intermediate_result: bool = True, 
                      enable_punctuation_prediction: bool = True,
                      enable_inverse_text_normalization: bool = True) -> bool:
        """
        启动WebSocket流式转写
        
        Args:
            enable_intermediate_result: 是否启用中间结果，默认为True
            enable_punctuation_prediction: 是否启用标点预测，默认为True
            enable_inverse_text_normalization: 是否启用逆文本规范化，默认为True
            
        Returns:
            是否成功启动流式转写
        """
        if not self.ws_url:
            logger.error("WebSocket URL not available. Create a task first.")
            return False
            
        logger.info(f"Starting WebSocket connection to: {self.ws_url}")
        
        try:
            # 从 WebSocket URL 中提取token
            url_parts = urllib.parse.urlparse(self.ws_url)
            query_params = urllib.parse.parse_qs(url_parts.query)
            token = query_params.get('mc', [None])[0]
            
            if not token:
                logger.error("Failed to extract token from WebSocket URL")
                return False
                
            logger.debug(f"Extracted token: {token[:10]}...")
            
            # 使用提取的token和app_key初始化转写器
            # 在初始化时直接传入回调函数
            self.transcriber = nls.NlsRealtimeMeeting(
                url=self.ws_url,
                on_start=self._on_transcription_start,
                on_sentence_begin=self._on_sentence_begin,
                on_sentence_end=self._on_sentence_end,
                on_result_changed=self._on_result_changed,
                on_completed=self._on_transcription_completed,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # 其他参数在start方法中设置
            self.transcriber.start()
            self.is_streaming = True
            logger.info("WebSocket stream started successfully\n---")
            return True
                
        except Exception as e:
            logger.error(f"Error starting streaming: {str(e)}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return False
    
    def send_audio_data(self, audio_data: bytes) -> bool:
        """
        发送音频数据
        
        Args:
            audio_data: PCM格式的音频数据
            
        Returns:
            是否成功发送
        """
        if not self.transcriber:
            logger.error("Transcriber not initialized")
            return False
        
        if not self.is_streaming:
            logger.warning("Not streaming, but trying to send audio data anyway")
        
        try:
            # 发送音频数据
            # 注意：NlsSpeechTranscriber.send_audio的第一个参数是音频数据，没有其他参数
            self.transcriber.send_audio(audio_data)
            return True
        except Exception as e:
            logger.error(f"Error sending audio data: {str(e)}")
            return False
    
    def stop_streaming(self) -> bool:
        """
        停止WebSocket流式转写
        
        Returns:
            是否成功停止
        """
        logger.info("Stopping WebSocket streaming")
        
        if not self.transcriber:
            logger.warning("No active transcriber to stop")
            return False
        
        try:
            # 停止转写
            self.transcriber.stop()
            self.transcriber.shutdown()
            self.is_streaming = False
            logger.info("WebSocket streaming stopped successfully")
            return True
        except Exception as e:
            logger.error(f"Error stopping streaming: {str(e)}")
            return False
    
    def end_task(self) -> Dict:
        """
        结束通义听悟任务
        
        Returns:
            包含API响应的字典
        """
        if not self.task_id:
            logger.error("No active task to end")
            raise Exception("No active task to end")
            
        logger.info(f"Ending task with ID: {self.task_id}")
        
        # 确保WebSocket已关闭
        if self.transcriber and self.is_streaming:
            logger.warning("WebSocket still streaming. Stopping it first.")
            self.stop_streaming()
        
        # 对于通义听悟实时流式转写，通过关闭WebSocket连接来结束任务
        # 不需要额外调用HTTP API
        
        # 返回成功状态
        logger.info("Task considered ended successfully after WebSocket closure")
        return {"Status": "Success", "Message": "Task ended by closing WebSocket connection"}
    
    def get_task_info(self) -> Dict:
        """
        获取任务信息
        
        Returns:
            包含任务信息的字典
        """
        if not self.task_id:
            logger.error("No task ID available")
            raise Exception("No task ID available")
            
        logger.info(f"Getting info for task with ID: {self.task_id}")
        
        # 返回本地状态
        ws_status = {
            "is_connected": self.is_connected,
            "is_streaming": self.is_streaming,
            "task_id": self.task_id,
            "ws_url": self.ws_url
        }
        
        logger.info("Returning local state instead of calling API")
        return {
            "Status": "Success",
            "TaskId": self.task_id,
            "WebSocketStatus": ws_status,
            "Message": "Task info retrieved from local state"
        }
    
    # NlsSpeechTranscriber 回调方法
    def _on_transcription_start(self, message, *args):
        """转写开始回调"""
        logger.info(f"Transcription started: {message}")
        self.is_connected = True
        if self.on_connection_open:
            self.on_connection_open()
    
    def _on_sentence_begin(self, message, *args):
        """句子开始回调"""
        logger.debug(f"Sentence began: {message}")
        if self.on_sentence_begin:
            self.on_sentence_begin(message)
    
    def _on_sentence_end(self, message, *args):
        """句子结束回调"""
        logger.debug(f"Sentence ended: {message}")
        if self.on_sentence_end:
            self.on_sentence_end(message)
    
    def _on_result_changed(self, message, *args):
        """结果变化回调"""
        try:
            # 解析JSON消息
            result_obj = json.loads(message)
            result = result_obj.get('payload', {}).get('result', '')
            is_final = result_obj.get('payload', {}).get('final', False)
            confidence = result_obj.get('payload', {}).get('confidence', 0.0)
            
            logger.debug(f"Result changed: '{result}' (final: {is_final}, confidence: {confidence})")
            
            # 调用用户回调
            if self.on_result:
                self.on_result(result, is_final, confidence)
        except Exception as e:
            logger.error(f"Error processing result: {str(e)}")
    
    def _on_transcription_completed(self, message, *args):
        """转写完成回调"""
        logger.info(f"Transcription completed: {message}")
        if self.on_completed:
            self.on_completed(message)
    
    def _on_error(self, message, *args):
        """错误回调"""
        logger.error(f"Error occurred: {message}")
        if self.on_error:
            self.on_error(message)
    
    def _on_close(self, *args):
        """连接关闭回调"""
        logger.info("WebSocket connection closed")
        self.is_connected = False
        self.is_streaming = False
        if self.on_connection_close:
            self.on_connection_close()
    
    def _create_common_request(self, domain: str, version: str, protocol_type: str, method: str, uri: str) -> CommonRequest:
        """
        创建通用请求对象
        
        Args:
            domain: 域名
            version: API版本
            protocol_type: 协议类型
            method: HTTP方法
            uri: URI路径
            
        Returns:
            CommonRequest对象
        """
        request = CommonRequest()
        request.set_domain(domain)
        request.set_version(version)
        request.set_protocol_type(protocol_type)
        request.set_method(method)
        request.set_uri_pattern(uri)
        request.set_accept_format('json')
        request.add_header('Content-Type', 'application/json;charset=UTF-8')
        
        return request
