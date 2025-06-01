"""
TouchDesigner组件中处理WebSocket连接和显示转写结果的脚本
"""

import json
import traceback
import logging
from TDStoreTools import StorageManager
TDF = op.TDModules.mod.TDFunctions

# 设置专业的logger
class TDLogger:
    def __init__(self, log_node):
        self.log_node = log_node
        self.logger = logging.getLogger("TingwuReceiver")
        self.logger.setLevel(logging.INFO)
        
        # 添加处理器来将日志记录到TouchDesigner表格中
        self.td_handler = TDLogHandler(log_node)
        self.td_handler.setLevel(logging.INFO)
        self.logger.addHandler(self.td_handler)
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

class TDLogHandler(logging.Handler):
    def __init__(self, log_node):
        super().__init__()
        self.log_node = log_node
    
    def emit(self, record):
        try:
            level = record.levelname
            message = self.format(record)
            if self.log_node:
                self.log_node.appendRow([level, message])
        except Exception:
            self.handleError(record)

# 用于存储设置和数据
class TingwuReceiver:
    def __init__(self, ownerComp):
        try:
            # 存储组件
            self.ownerComp = ownerComp
            print("TingwuReceiver initialized successfully!")
            
            # # 初始化日志
            # self.log_node = op('log')
            # self.td_logger = TDLogger(self.log_node)
            # self.logger = self.td_logger.logger
            
            # # 存储管理器设置
            # storageName = "TingwuReceiverData"
            # self.stored_data = StorageManager(self, ownerComp, storageName)
            
            # # 初始数据设置
            # default_data = {
            #     "ws_host": "127.0.0.1",
            #     "ws_port": 8765,
            #     "current_text": "",
            #     "is_connected": False,
            #     "connection_status": "Disconnected",
            #     "reconnect_attempts": 0,
            #     "max_reconnect_attempts": 5,
            # }
            
            # # 初始化存储
            # self.stored_data.Initialize(default_data)
            
            # self.logger.info("TingwuReceiver initialized")
            
            # # 关联WebSocket连接节点
            # self.ws_node = self.ownerComp.op('websocket1')
            
            # # 确保UI正确显示初始状态
            # self.update_ui()
        except Exception as e:
            print(f"Error initializing TingwuReceiver: {str(e)}")
    
    def connect(self):
        """连接到WebSocket服务器"""
        try:
            ws_host = self.stored_data['ws_host']
            ws_port = self.stored_data['ws_port']
            
            # 更新连接状态
            self.stored_data['connection_status'] = "Connecting..."
            self.update_ui()
            
            # 设置WebSocket URL并连接
            ws_url = f"ws://{ws_host}:{ws_port}"
            self.ws_node.par.Active = False  # 先断开现有连接
            self.ws_node.par.Address = ws_url
            self.ws_node.par.Active = True   # 开始新连接
            
            self.logger.info(f"Connecting to WebSocket server at {ws_url}")
        except Exception as e:
            self.logger.error(f"Error connecting to WebSocket: {str(e)}")
            self.stored_data['connection_status'] = f"Connection Error: {str(e)}"
            self.update_ui()
    
    def disconnect(self):
        """断开WebSocket连接"""
        try:
            self.ws_node.par.Active = False
            self.stored_data['is_connected'] = False
            self.stored_data['connection_status'] = "Disconnected"
            self.update_ui()
            self.logger.info("Disconnected from WebSocket server")
        except Exception as e:
            self.logger.error(f"Error disconnecting: {str(e)}")
    
    def on_ws_connect(self):
        """WebSocket连接成功回调"""
        self.stored_data['is_connected'] = True
        self.stored_data['connection_status'] = "Connected"
        self.stored_data['reconnect_attempts'] = 0
        self.update_ui()
        self.logger.info("Connected to WebSocket server")
    
    def on_ws_disconnect(self):
        """WebSocket断开连接回调"""
        self.stored_data['is_connected'] = False
        self.stored_data['connection_status'] = "Disconnected"
        self.update_ui()
        self.logger.info("Disconnected from WebSocket server")
        
        # 尝试自动重连
        self.try_reconnect()
    
    def try_reconnect(self):
        """尝试重新连接WebSocket"""
        if self.stored_data['reconnect_attempts'] < self.stored_data['max_reconnect_attempts']:
            self.stored_data['reconnect_attempts'] += 1
            attempts = self.stored_data['reconnect_attempts']
            max_attempts = self.stored_data['max_reconnect_attempts']
            
            self.logger.info(f"Attempting to reconnect ({attempts}/{max_attempts})...")
            self.stored_data['connection_status'] = f"Reconnecting ({attempts}/{max_attempts})..."
            self.update_ui()
            
            # 设置重连定时器
            run("op('{}').connect()".format(self.ownerComp.path), delayFrames=30)
        else:
            self.logger.warning("Maximum reconnection attempts reached")
            self.stored_data['connection_status'] = "Reconnection failed"
            self.update_ui()
    
    def on_ws_message(self, data):
        """处理接收到的WebSocket消息"""
        try:
            # 解析JSON数据
            message = json.loads(data)
            
            # 如果是转写结果
            if "text" in message:
                self.stored_data['current_text'] = message["text"]
                
                # 根据是否是最终结果决定文本颜色
                is_final = message.get("is_final", False)
                
                # 更新文本显示
                text_node = op('text_display')
                if text_node:
                    text_node.text = self.stored_data['current_text']
                    text_node.par.bgcolorr = 0.2 if is_final else 0.1
                    text_node.par.bgcolorg = 0.5 if is_final else 0.2
                    text_node.par.bgcolorb = 0.2 if is_final else 0.1
                
                # 在日志中记录信息（但不要太频繁，可能导致性能问题）
                if is_final:
                    self.logger.info(f"Final result: {self.stored_data['current_text']}")
            
            # 如果是状态消息
            elif "status" in message:
                if message["status"] == "completed":
                    self.logger.info("Transcription completed")
                elif message["status"] == "error":
                    self.logger.error(f"Error: {message.get('message', 'Unknown error')}")
        
        except json.JSONDecodeError:
            self.logger.error(f"Received invalid JSON data: {data}")
        except Exception as e:
            self.logger.error(f"Error processing WebSocket message: {str(e)}")
            self.logger.error(traceback.format_exc())
    
    def update_ui(self):
        """更新UI显示"""
        # 更新连接状态文本
        status_text = op('connection_status')
        if status_text:
            status_text.text = self.stored_data['connection_status']
            
            # 根据连接状态设置颜色
            if self.stored_data['is_connected']:
                status_text.par.bgcolorr = 0.0
                status_text.par.bgcolorg = 0.5
                status_text.par.bgcolorb = 0.0
            elif "Connecting" in self.stored_data['connection_status']:
                status_text.par.bgcolorr = 0.5
                status_text.par.bgcolorg = 0.5
                status_text.par.bgcolorb = 0.0
            else:
                status_text.par.bgcolorr = 0.5
                status_text.par.bgcolorg = 0.0
                status_text.par.bgcolorb = 0.0
        
        # 更新连接按钮状态
        connect_button = op('connect_button')
        if connect_button:
            connect_button.par.display = not self.stored_data['is_connected']
        
        disconnect_button = op('disconnect_button')
        if disconnect_button:
            disconnect_button.par.display = self.stored_data['is_connected']
    
    def update_settings(self):
        """从UI更新设置"""
        try:
            host_field = op('host_field')
            port_field = op('port_field')
            
            if host_field and host_field.text:
                self.stored_data['ws_host'] = host_field.text
            
            if port_field and port_field.text:
                try:
                    self.stored_data['ws_port'] = int(port_field.text)
                except ValueError:
                    self.logger.error("Invalid port number")
            
            self.logger.info(f"Settings updated: {self.stored_data['ws_host']}:{self.stored_data['ws_port']}")
        except Exception as e:
            self.logger.error(f"Error updating settings: {str(e)}")
