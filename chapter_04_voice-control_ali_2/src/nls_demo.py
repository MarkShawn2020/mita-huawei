#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
通义听悟实时语音转写演示程序 - 使用官方NLS SDK实现
"""

import os
import time
import argparse
from typing import Dict, Optional, Any
from dotenv import load_dotenv

from tingwu_nls_sdk import TingwuNlsSDK
from audio_capture import AudioCapture
from logger import Logger

logger = Logger().logger

load_dotenv()

def on_result(result_text, is_sentence_end, begin_time_ms):
    """转写结果回调函数"""
    current_time = time.time()
    # 音频相对时间戳（从录音开始的毫秒数）
    time_relative = f"T+{begin_time_ms/1000:.2f}s" if begin_time_ms else "Unknown"
    
    # 打印结果，包含相对时间戳
    if is_sentence_end:
        print(f"\n[Final Result] [{time_relative}] {result_text}")
        logger.info(f"Final transcription result at {time_relative}: {result_text}")
    else:
        # 中间结果使用\r覆盖同一行
        print(f"\r[Interim Result] [{time_relative}] {result_text}", end="")
        logger.debug(f"Interim transcription result at {time_relative}: {result_text}")

def on_sentence_begin(message: Dict):
    """
    句子开始回调
    
    Args:
        message: 包含句子开始信息的字典
    """
    logger.debug(f"Sentence begin: {message}")

def on_sentence_end(message: Dict):
    """
    句子结束回调
    
    Args:
        message: 包含句子结束信息的字典
    """
    logger.debug(f"Sentence end: {message}")

def on_completed(message: Dict):
    """
    转写完成回调
    
    Args:
        message: 完成消息，包含任务信息
    """
    print("\nTranscription completed")
    print(f"Details: {message}")
    
    # 在转写完成时显示最终的延迟统计信息
    if 'sdk' in globals() and hasattr(sdk, 'get_latency_stats'):
        display_latency_stats()
    print("\nTranscription completed!")

def on_error(message: str):
    """
    错误回调
    
    Args:
        message: 错误信息
    """
    logger.error(f"Error: {message}")
    print(f"\nError occurred: {message}")

def display_latency_stats():
    """显示语音识别延迟统计信息"""
    # 使用全局变量
    global sdk
    
    if 'sdk' not in globals() or not hasattr(sdk, 'get_latency_stats'):
        print("Latency statistics not available.")
        return
        
    try:
        stats = sdk.get_latency_stats()
        if stats['count'] == 0:
            print("No latency data available yet.")
            return
            
        print("\n" + "=" * 50)
        print("SPEECH RECOGNITION LATENCY STATISTICS")
        print("=" * 50)
        print(f"Total samples: {stats['count']}")
        print(f"Average latency: {stats['average_ms']:.2f} ms")
        print(f"Minimum latency: {stats['min_ms']:.2f} ms")
        print(f"Maximum latency: {stats['max_ms']:.2f} ms")
        
        if 'p50_ms' in stats:
            print(f"50th percentile: {stats['p50_ms']:.2f} ms")
            print(f"95th percentile: {stats['p95_ms']:.2f} ms")
            print(f"99th percentile: {stats['p99_ms']:.2f} ms")
            
        print("=" * 50)
    except Exception as e:
        logger.error(f"Error displaying latency stats: {str(e)}")
        print(f"Error displaying latency stats: {str(e)}")

def on_connection_open():
    """连接打开回调"""
    print("\nWebSocket connection opened and ready to stream audio")

def on_connection_close():
    """连接关闭回调"""
    print("\nWebSocket connection closed - will try to reconnect if still recording")

def main():
    """使用通义听悟SDK演示实时语音转写的主函数"""
    parser = argparse.ArgumentParser(description="Demo for Alibaba Tingwu Real-time Speech-to-Text")
    parser.add_argument('--access-key-id', help='Alibaba Cloud Access Key ID')
    parser.add_argument('--access-key-secret', help='Alibaba Cloud Access Key Secret')
    parser.add_argument('--app-key', help='Tingwu App Key')
    parser.add_argument('--language', default='cn', help='Source language (default: cn)')
    parser.add_argument('--enable-translation', action='store_true', help='Enable translation')
    parser.add_argument('--target-language', default='en', help='Target language for translation')
    parser.add_argument('--sample-rate', type=int, default=16000, help='Audio sample rate (8000 or 16000)')
    # todo: 可以升级为多长时间没有声音就停止程序
    parser.add_argument('--duration', type=int, default=5, help='Recording duration in seconds')
    args = parser.parse_args()
    
    # 从命令行参数或环境变量获取密钥
    access_key_id = args.access_key_id or os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID')
    access_key_secret = args.access_key_secret or os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
    app_key = args.app_key or os.environ.get('TINGWU_APP_KEY')
    
    logger.info("Credentials loaded" + (" successfully" if all([access_key_id, access_key_secret, app_key]) else " with missing values"))
    
    if not access_key_id or not access_key_secret or not app_key:
        print("Error: Missing credentials. Please provide them as arguments or environment variables.")
        return
    
    # 创建通义听悟SDK实例
    sdk = TingwuNlsSDK(access_key_id, access_key_secret, app_key)
    
    # 设置回调函数
    sdk.set_callbacks(
        on_result=on_result,
        on_sentence_begin=on_sentence_begin,
        on_sentence_end=on_sentence_end,
        on_completed=on_completed,
        on_error=on_error,
        on_connection_open=on_connection_open,
        on_connection_close=on_connection_close
    )
    
    try:
        # 创建任务
        task_info = sdk.create_task(
            source_language=args.language,
            format="pcm",  # 固定为PCM格式
            sample_rate=args.sample_rate,
            # 如果需要翻译，添加相关参数
            enable_translation=args.enable_translation,
            target_languages=[args.target_language] if args.enable_translation else None
        )
        
        # task_info 形式为 {'Code': '0', 'Data': {'TaskId': '...', 'MeetingJoinUrl': '...'}, ...}
        if 'Data' in task_info:
            task_id = task_info['Data'].get('TaskId')
            ws_url = task_info['Data'].get('MeetingJoinUrl')
            
            print(f"Task created with ID: {task_id}")
            print(f"WebSocket URL: {ws_url}")
        else:
            # 如果没有Data字段，直接使用对象属性
            print(f"Task created with ID: {sdk.task_id}")
            print(f"WebSocket URL: {sdk.ws_url}")
        
        # 启动WebSocket连接
        if not sdk.start_streaming(
            enable_intermediate_result=True,  # 始终启用中间结果
            enable_punctuation_prediction=True,  # 始终启用标点预测
            enable_inverse_text_normalization=True  # 始终启用逆文本规范化
        ):
            logger.error("Failed to start WebSocket connection")
            return
        
        # 初始化音频捕获
        audio_capture = AudioCapture(
            rate=args.sample_rate,
            channels=1,
            chunk_size=1024
        )
                # Set up callback for audio data
        audio_capture.set_audio_callback(sdk.send_audio_data)
        
        print("\nStarting microphone recording...")
        print(f"Recording for {args.duration} seconds. Speak now...")
        
        # 开始捕获音频
        audio_capture.start()
        
        # 定期显示延迟统计信息
        start_time = time.time()
        display_interval = 5  # 每5秒显示一次统计信息
        next_display = start_time + display_interval
        
        # 等待录音完成，同时定期显示统计信息
        while audio_capture.is_recording:
            current_time = time.time()
            if current_time >= next_display:
                print("\n--- Current Latency Statistics ---")
                display_latency_stats()
                next_display = current_time + display_interval
            time.sleep(0.1)  # 避免CPU过度使用
        
        # 停止流式转写
        sdk.stop_streaming()
        
        # 显示最终的延迟统计信息
        print("\n--- Final Latency Statistics ---")
        display_latency_stats()
        
        # 结束任务
        print("Ending task...")
        task_status = sdk.end_task()
        print(f"Task status: {task_status.get('Status')}")
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
