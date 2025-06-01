#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
通义听悟实时语音转写演示程序 - 使用官方NLS SDK实现
集成WebSocket服务器用于与TouchDesigner通信
"""

import os
import time
import argparse
import asyncio
import threading
import websockets
import json
from typing import Dict, Set
from dotenv import load_dotenv

from core.tingwu_sdk.nls import TingwuNlsSDK
from core.audio_capture import AudioCapture
from utils.logger import Logger

logger = Logger().logger

# 全局WebSocket客户端集合
websocket_clients: Set[websockets.WebSocketServerProtocol] = set()

# 用于实时转写结果的最新状态
current_result = {
    "text": "",
    "is_final": False,
    "begin_time": 0,
    "timestamp": 0
}

def on_result(result_text, is_sentence_end, begin_time_ms):
    """转写结果回调函数"""
    global current_result
    
    logger.info(f"[on result] {result_text}")
    
    # 更新当前结果
    current_result["text"] = result_text
    current_result["is_final"] = is_sentence_end
    current_result["begin_time"] = begin_time_ms
    current_result["timestamp"] = time.time()
    
    # 通过WebSocket发送结果给TouchDesigner
    message = json.dumps(current_result)
    asyncio.run(send_to_td(message))

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
    
    # 通知TouchDesigner转写已完成
    complete_message = {
        "status": "completed",
        "details": message
    }
    asyncio.run(send_to_td(json.dumps(complete_message)))

def on_error(message: str):
    """
    错误回调
    
    Args:
        message: 错误信息
    """
    logger.error(f"Error: {message}")
    print(f"\nError occurred: {message}")
    
    # 通知TouchDesigner发生错误
    error_message = {
        "status": "error",
        "message": message
    }
    asyncio.run(send_to_td(json.dumps(error_message)))

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

# WebSocket服务器处理函数
async def ws_handler(websocket, path):
    """处理WebSocket连接"""
    # 注册新客户端
    websocket_clients.add(websocket)
    logger.info(f"New WebSocket client connected: {websocket.remote_address}")
    
    # 发送当前状态给新连接的客户端
    await websocket.send(json.dumps(current_result))
    
    try:
        # 保持连接直到客户端断开
        async for message in websocket:
            # 处理来自TouchDesigner的消息（如果有）
            data = json.loads(message)
            logger.debug(f"Received message from TouchDesigner: {data}")
            
            # 可以在这里处理来自TouchDesigner的命令
            if "command" in data:
                if data["command"] == "get_status":
                    # 发送当前状态
                    await websocket.send(json.dumps(current_result))
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket connection closed normally")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        # 客户端断开连接，从集合中移除
        websocket_clients.remove(websocket)
        logger.info(f"WebSocket client disconnected: {websocket.remote_address}")

# 发送消息给所有TouchDesigner客户端
async def send_to_td(message):
    """发送消息给所有连接的TouchDesigner客户端"""
    if websocket_clients:  # 如果有连接的客户端
        # 创建发送任务列表
        tasks = [client.send(message) for client in websocket_clients]
        # 并行执行所有发送任务
        await asyncio.gather(*tasks, return_exceptions=True)

# 启动WebSocket服务器
def start_websocket_server(host="127.0.0.1", port=8765):
    """启动WebSocket服务器线程"""
    logger.info(f"Starting WebSocket server on {host}:{port}")
    
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # 创建WebSocket服务器
    start_server = websockets.serve(ws_handler, host, port)
    
    # 运行服务器直到完成（不会完成，除非关闭）
    loop.run_until_complete(start_server)
    logger.info(f"WebSocket server started on ws://{host}:{port}")
    
    # 一直运行事件循环
    loop.run_forever()

def main():
    """使用通义听悟SDK演示实时语音转写的主函数"""
    parser = argparse.ArgumentParser(description="Demo for Alibaba Tingwu Real-time Speech-to-Text with WebSocket for TouchDesigner")
    parser.add_argument('--access-key-id', help='Alibaba Cloud Access Key ID')
    parser.add_argument('--access-key-secret', help='Alibaba Cloud Access Key Secret')
    parser.add_argument('--app-key', help='Tingwu App Key')
    parser.add_argument('--language', default='cn', help='Source language (default: cn)')
    parser.add_argument('--enable-translation', action='store_true', help='Enable translation')
    parser.add_argument('--target-language', default='en', help='Target language for translation')
    parser.add_argument('--sample-rate', type=int, default=16000, help='Audio sample rate (8000 or 16000)')
    parser.add_argument('--duration', type=int, default=0, help='Recording duration in seconds (0 for infinite)')
    parser.add_argument('--ws-host', default='127.0.0.1', help='WebSocket server host')
    parser.add_argument('--ws-port', type=int, default=8765, help='WebSocket server port')
    args = parser.parse_args()
    
    # 从命令行参数或环境变量获取密钥
    access_key_id = args.access_key_id or os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID')
    access_key_secret = args.access_key_secret or os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
    app_key = args.app_key or os.environ.get('TINGWU_APP_KEY')
    
    logger.info("Credentials loaded" + (" successfully" if all([access_key_id, access_key_secret, app_key]) else " with missing values"))
    
    if not access_key_id or not access_key_secret or not app_key:
        print("Error: Missing credentials. Please provide them as arguments or environment variables.")
        return
    
    # 启动WebSocket服务器线程
    ws_thread = threading.Thread(
        target=start_websocket_server,
        args=(args.ws_host, args.ws_port),
        daemon=True
    )
    ws_thread.start()
    logger.info(f"WebSocket server thread started on ws://{args.ws_host}:{args.ws_port}")
    
    # 创建通义听悟SDK实例
    global sdk
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
        if args.duration > 0:
            print(f"Recording for {args.duration} seconds. Speak now...")
        else:
            print("Recording indefinitely. Press Ctrl+C to stop. Speak now...")
        
        # 开始捕获音频
        audio_capture.start()
        
        # 定期显示延迟统计信息
        start_time = time.time()
        display_interval = 5  # 每5秒显示一次统计信息
        next_display = start_time + display_interval
        
        try:
            # 如果设置了持续时间，就只录制指定的时间
            if args.duration > 0:
                end_time = start_time + args.duration
                while time.time() < end_time:
                    # 显示统计信息
                    if time.time() >= next_display:
                        if hasattr(sdk, 'get_latency_stats'):
                            display_latency_stats()
                        next_display = time.time() + display_interval
                    time.sleep(0.1)
            else:
                # 无限录制，直到用户中断
                try:
                    while True:
                        # 显示统计信息
                        if time.time() >= next_display:
                            if hasattr(sdk, 'get_latency_stats'):
                                display_latency_stats()
                            next_display = time.time() + display_interval
                        time.sleep(0.1)
                except KeyboardInterrupt:
                    print("\nRecording stopped by user")
        finally:
            # 停止录音
            audio_capture.stop()
            
            # 停止流式转写
            sdk.stop_streaming()
            
            # 显示最终统计信息
            if hasattr(sdk, 'get_latency_stats'):
                display_latency_stats()
            
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main()
