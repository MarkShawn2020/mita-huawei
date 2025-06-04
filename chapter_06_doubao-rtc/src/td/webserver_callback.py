import logging
import json
from datetime import datetime
import time

# 配置共享的专业 logger
logger = logging.getLogger('webserver_callback')
logger.setLevel(logging.INFO)

# 如果没有handler，创建一个
if not logger.handlers:
	handler = logging.StreamHandler()
	formatter = logging.Formatter(
		'%(asctime)s - %(levelname)s - %(message)s'
	)
	handler.setFormatter(formatter)
	logger.addHandler(handler)

# 用于追踪消息去重和流式合并
last_message_cache = {}
last_log_time = {}

# return the response dictionary
def onHTTPRequest(webServerDAT, request, response):
	try:
		method = request.get('method', 'Unknown')
		uri = request.get('uri', 'Unknown')
		logger.info(f" HTTP {method} {uri}")
		
		response['statusCode'] = 200
		response['statusReason'] = 'OK'
		response['data'] = '<b>TouchDesigner: </b>' + webServerDAT.name
		return response
	except Exception as e:
		logger.error(f" HTTP Error: {str(e)}")
		response['statusCode'] = 500
		response['statusReason'] = 'Internal Server Error'
		response['data'] = 'Server Error'
		return response

def onWebSocketOpen(webServerDAT, client, uri):
	try:
		client_info = getattr(client, 'address', 'Unknown') if hasattr(client, 'address') else 'Unknown'
		logger.info(f" WebSocket connected: {client_info}")
	except Exception as e:
		logger.error(f" WebSocket open error: {str(e)}")
	return

def onWebSocketClose(webServerDAT, client):
	try:
		client_info = getattr(client, 'address', 'Unknown') if hasattr(client, 'address') else 'Unknown'
		logger.info(f" WebSocket disconnected: {client_info}")
	except Exception as e:
		logger.error(f" WebSocket close error: {str(e)}")
	return

def onWebSocketReceiveText(webServerDAT, client, data):
	try:
		client_info = getattr(client, 'address', 'Unknown') if hasattr(client, 'address') else 'Unknown'
		
		# 尝试解析JSON数据
		try:
			message_data = json.loads(data)
			message_type = message_data.get('type', 'unknown')
			current_time = time.time()
			
			# 根据消息类型记录详细信息
			if message_type == 'ai_message':
				user = message_data.get('user', 'Unknown')
				text = message_data.get('text', '')
				timestamp = message_data.get('timestamp', 0)
				
				# 流式消息去重：如果是相同用户的连续消息且时间间隔很短，只记录重要节点
				cache_key = f"{user}_ai"
				should_log = True
				
				if cache_key in last_message_cache:
					last_text = last_message_cache[cache_key].get('text', '')
					last_time = last_log_time.get(cache_key, 0)
					
					# 如果是增量更新且时间间隔小于1秒，跳过大部分日志
					if text.startswith(last_text) and (current_time - last_time) < 1.0:
						# 只在句子结束时记录
						if not (text.endswith('.') or text.endswith('。') or text.endswith('!') or text.endswith('！') or text.endswith('?') or text.endswith('？')):
							should_log = False
				
				if should_log:
					logger.info(f" {user}: {text}")
					last_message_cache[cache_key] = {'text': text}
					last_log_time[cache_key] = current_time
				
			elif message_type == 'user_message':
				user = message_data.get('user', 'Unknown')
				text = message_data.get('text', '')
				
				# 用户消息去重
				cache_key = f"{user}_user"
				if cache_key not in last_message_cache or last_message_cache[cache_key].get('text') != text:
					logger.info(f" {user}: {text}")
					last_message_cache[cache_key] = {'text': text}
				
			elif message_type == 'status_update':
				status = message_data.get('status', 'unknown')
				
				# 状态更新去重
				cache_key = "status"
				if cache_key not in last_message_cache or last_message_cache[cache_key].get('status') != status:
					status_emoji = {'idle': '', 'thinking': '', 'speaking': '', 'listening': ''}.get(status, '')
					logger.info(f"{status_emoji} Status: {status}")
					last_message_cache[cache_key] = {'status': status}
				
			elif message_type == 'audio_data':
				volume = message_data.get('volume', 0)
				# 音频数据只在音量变化显著时记录
				cache_key = "audio"
				last_volume = last_message_cache.get(cache_key, {}).get('volume', 0)
				if abs(volume - last_volume) > 0.1:  # 音量变化超过0.1才记录
					logger.debug(f" Audio: vol={volume:.2f}")
					last_message_cache[cache_key] = {'volume': volume}
				
			else:
				logger.debug(f" Unknown message type: {message_type}")
				
		except json.JSONDecodeError:
			logger.debug(f" Non-JSON data: {data[:50]}{'...' if len(data) > 50 else ''}")
		
		# 回传数据（不记录日志避免冗余）
		webServerDAT.webSocketSendText(client, data)
		
	except Exception as e:
		logger.error(f" Error in onWebSocketReceiveText: {str(e)}")
	return

def onWebSocketReceiveBinary(webServerDAT, client, data):
	try:
		logger.debug(f" Binary data: {len(data)} bytes")
		webServerDAT.webSocketSendBinary(client, data)
	except Exception as e:
		logger.error(f" Binary error: {str(e)}")
	return

def onWebSocketReceivePing(webServerDAT, client, data):
	try:
		webServerDAT.webSocketSendPong(client, data=data)
		logger.debug(f" Ping/Pong")
	except Exception as e:
		logger.error(f" Ping error: {str(e)}")
	return

def onWebSocketReceivePong(webServerDAT, client, data):
	try:
		logger.debug(f" Pong received")
	except Exception as e:
		logger.error(f" Pong error: {str(e)}")
	return

def onServerStart(webServerDAT):
	try:
		logger.info(f" Server started: {webServerDAT.name}")
	except Exception as e:
		logger.error(f" Server start error: {str(e)}")
	return

def onServerStop(webServerDAT):
	try:
		logger.info(f" Server stopped: {webServerDAT.name}")
	except Exception as e:
		logger.error(f" Server stop error: {str(e)}")
	return