# speechModule/aliyun_api_logic (Text DAT)

import os
import json
import datetime
import struct # 用于将float转为16-bit PCM bytes

# 尝试导入阿里云SDK
try:
    from aliyunsdkcore.client import AcsClient
    from aliyunsdkcore.request import CommonRequest
    from aliyunsdkcore.auth.credentials import AccessKeyCredential
    ALIYUN_SDK_AVAILABLE = True
except ImportError:
    ALIYUN_SDK_AVAILABLE = False
    print("ERROR: Aliyun SDK (aliyun-python-sdk-core) not found. Please install it.")
    # 在TouchDesigner的Python环境中: C:\Program Files\Derivative\TouchDesigner\bin\python.exe -m pip install aliyun-python-sdk-core

# ownerComp 指向 speechModule Base COMP
ownerComp = me.parent()

def get_credentials_and_client():
    """获取API凭证和AcsClient实例"""
    if not ALIYUN_SDK_AVAILABLE:
        raise Exception("Aliyun SDK not available.")
    
    access_key_id = ownerComp.par.Accesskeyid.eval()
    access_key_secret = ownerComp.par.Accesskeysecret.eval()
    app_key = ownerComp.par.Appkey.eval()
    region_id = ownerComp.par.Regionid.eval()

    if not all([access_key_id, access_key_secret, app_key, region_id]):
        current_missing = []
        if not access_key_id: current_missing.append("AccessKeyID")
        if not access_key_secret: current_missing.append("AccessKeySecret")
        if not app_key: current_missing.append("AppKey")
        if not region_id: current_missing.append("RegionID")
        raise ValueError(f"API credentials missing in speechModule parameters: {', '.join(current_missing)}")
        
    credentials = AccessKeyCredential(access_key_id, access_key_secret)
    # 阿里云SDK通常会从环境变量读取区域，但明确指定更好
    # 确保 region_id 是有效的，例如 'cn-beijing', 'cn-shanghai' 等
    client = AcsClient(region_id=region_id, credential=credentials) 
    return client, app_key, region_id

def create_api_request(domain, version, protocol, method, uri_pattern):
    """辅助函数，创建阿里云 CommonRequest 对象"""
    request = CommonRequest()
    request.set_accept_format('json')
    request.set_domain(domain)
    request.set_version(version)
    request.set_protocol_type(protocol)
    request.set_method(method)
    request.set_uri_pattern(uri_pattern)
    request.add_header('Content-Type', 'application/json')
    return request

def convert_float_to_pcm16_bytes(float_samples_dat):
    """
    将 CHOP To DAT 输出的浮点样本 (-1.0 to 1.0) 转换为 16-bit PCM 字节流.
    假设 float_samples_dat 的第一列是音频数据。
    """
    byte_data = bytearray()
    if not float_samples_dat or float_samples_dat.numRows == 0:
        return bytes(byte_data)

    for i in range(float_samples_dat.numRows):
        sample_val_str = float_samples_dat[i, 0].val # 假设音频数据在第一列
        try:
            float_val = float(sample_val_str)
            # 将 float (-1.0 to 1.0) 转换为 16-bit signed int (-32768 to 32767)
            scaled_val = int(max(-1.0, min(1.0, float_val)) * 32767)
            # 打包为2字节，小端序 ('<h')
            byte_data.extend(struct.pack('<h', scaled_val))
        except ValueError:
            # print(f"Warning: Could not convert '{sample_val_str}' to float at row {i}.")
            pass 
    return bytes(byte_data)

# --- 主逻辑函数 ---

def EnsureRecognitionSessionActive():
    """
    创建阿里云HTTP实时记录任务并尝试连接WebSocket。
    由 VAD OffToOn (当 speechModule.par.Recognize=True 且无当前任务时) 调用。
    返回 True 如果HTTP任务创建成功并且已尝试启动WebSocket连接，否则 False。
    """
    ownerComp.op('stt_status_text').text = "Status: Creating Task..."
    try:
        client, app_key, region_id = get_credentials_and_client()
    except Exception as e:
        ownerComp.op('stt_status_text').text = f"Status: Credential Error - {e}"
        print(f"Error getting credentials for EnsureRecognitionSessionActive: {e}")
        return False

    # 构建CreateTask请求的body
    body = {
        'AppKey': app_key,
        'Input': {
            'Format': 'pcm',  # 我们将发送 PCM
            'SampleRate': 16000,
            'SourceLanguage': 'cn', # 或者 'en', 'yue', 'multilingual' 等
            'TaskKey': 'td_tingwu_task_' + datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'),
            'ProgressiveCallbacksEnabled': False # WebSocket直接返回结果
        },
        'Parameters': {
            'Transcription': {
                'OutputLevel': 2, # 1:完整句子, 2:中间结果+完整句子 (推荐实时用2)
                'DiarizationEnabled': False, # 按需开启说话人分离
                # 'PhraseId': 'your_hot_word_id' # 如果使用热词
            },
            # 'TranslationEnabled': False, # 按需开启翻译
            # 'Parameters.Translation.TargetLanguages': ['en'] # 如果开启翻译
        }
    }

    # 阿里云听悟 API 的域名通常是 tingwu.{region_id}.aliyuncs.com
    api_domain = f'tingwu.{region_id}.aliyuncs.com'
    
    request = create_api_request(
        api_domain,
        '2023-09-30', # API 版本，请根据最新文档确认
        'https',      # 协议
        'PUT',        # HTTP 方法
        '/openapi/tingwu/v2/tasks' # API路径
    )
    request.add_query_param('type', 'realtime')
    request.set_content(json.dumps(body).encode('utf-8'))

    try:
        print(f"Sending CreateTask request to {api_domain} with body: {json.dumps(body)}")
        response_str = client.do_action_with_exception(request)
        response_data = json.loads(response_str)
        print(f"CreateTask Response: {json.dumps(response_data, indent=2, ensure_ascii=False)}")

        if response_data.get("Code") == "0" and "Data" in response_data:
            task_id = response_data["Data"].get("TaskId")
            meeting_join_url = response_data["Data"].get("MeetingJoinUrl")

            if task_id and meeting_join_url:
                ownerComp.par.Taskid = task_id
                ownerComp.par.Websocketurl = meeting_join_url
                ownerComp.op('stt_status_text').text = f"Status: Task {task_id} Created. Connecting WS..."
                
                ws_client = ownerComp.op('stt_websocket_client')
                ws_client.par.active = True # 尝试连接WebSocket
                ws_client.par.netaddress = meeting_join_url
                return True # HTTP任务创建成功，已尝试启动WebSocket
            else:
                err_msg = "TaskId or MeetingJoinUrl missing in successful CreateTask response."
                ownerComp.op('stt_status_text').text = f"Status: API Error - {err_msg}"
                print(f"Error: {err_msg} Response: {response_data}")
        else:
            message = response_data.get("Message", "Unknown API error")
            code = response_data.get("Code", "N/A")
            ownerComp.op('stt_status_text').text = f"Status: API Error (Code: {code}) - {message}"
            print(f"API Error creating task: {message}, Code: {code}, Response: {response_data}")

    except Exception as e:
        ownerComp.op('stt_status_text').text = f"Status: CreateTask Exception - {e}"
        print(f"Exception during CreateTask: {e}")
    
    return False


def TerminateRecognitionSession():
    """
    关闭WebSocket连接并结束阿里云HTTP实时记录任务。
    由 speechModule.par.Recognize 变为 OFF 时，或发生严重错误时调用。
    """
    task_id_to_stop = ownerComp.par.Taskid.eval() # 获取当前准备停止的 TaskId

    # 1. 关闭 WebSocket
    ws_client = ownerComp.op('stt_websocket_client')
    if ws_client.par.active.eval():
        print(f"Closing WebSocket connection for TaskId: {task_id_to_stop if task_id_to_stop else 'N/A'}...")
        ws_client.par.active = False 
        # 理想情况下，等待 onDisconnect 回调确认，但这里简化处理

    # 2. 结束实时记录HTTP任务
    if not task_id_to_stop: # 如果 TaskId 已经为空，说明任务可能已被其他逻辑停止或从未成功创建
        print("TerminateRecognitionSession: No active TaskId to stop via API.")
        ownerComp.op('stt_status_text').text = "Status: No active task to stop."
        # 确保参数被清理
        ownerComp.par.Taskid = ""
        ownerComp.par.Websocketurl = ""
        return

    ownerComp.op('stt_status_text').text = f"Status: Stopping Task {task_id_to_stop} via API..."
    try:
        client, app_key, region_id = get_credentials_and_client()
    except Exception as e:
        ownerComp.op('stt_status_text').text = f"Status: Credential Error - {e}"
        print(f"Error getting credentials for TerminateRecognitionSession: {e}")
        # 即使获取凭证失败，也尝试清理本地参数
        ownerComp.par.Taskid = "" 
        ownerComp.par.Websocketurl = ""
        return

    # 构建StopTask请求的body (根据文档，似乎只需要 TaskId)
    body_stop = {
        # 'AppKey': app_key, # 文档示例未明确是否需要，但 CreateTask 的Python示例有
        'Input': { # 根据文档，结束任务的 PUT 请求 body 可能只需要 TaskId
            'TaskId': task_id_to_stop
        }
    }
    
    api_domain = f'tingwu.{region_id}.aliyuncs.com'

    request_stop = create_api_request(
        api_domain,
        '2023-09-30', # API 版本
        'https',
        'PUT',
        '/openapi/tingwu/v2/tasks' # 与CreateTask相同的路径
    )
    request_stop.add_query_param('type', 'realtime')
    request_stop.add_query_param('operation', 'stop') # 关键参数，表示停止操作
    request_stop.set_content(json.dumps(body_stop).encode('utf-8'))

    try:
        print(f"Sending StopTask request for TaskId: {task_id_to_stop} with body: {json.dumps(body_stop)}")
        response_str_stop = client.do_action_with_exception(request_stop)
        response_data_stop = json.loads(response_str_stop)
        print(f"StopTask Response: {json.dumps(response_data_stop, indent=2, ensure_ascii=False)}")

        if response_data_stop.get("Code") == "0" and "Data" in response_data_stop:
            status = response_data_stop["Data"].get("TaskStatus", "N/A")
            ownerComp.op('stt_status_text').text = f"Status: Task {task_id_to_stop} Stopped. API Status: {status}"
        else:
            message = response_data_stop.get("Message", "Unknown error stopping task")
            code = response_data_stop.get("Code", "N/A")
            ownerComp.op('stt_status_text').text = f"Status: API Error (Code: {code}) stopping {task_id_to_stop} - {message}"
            print(f"API Error stopping task {task_id_to_stop}: {message}, Code: {code}, Response: {response_data_stop}")

    except Exception as e:
        ownerComp.op('stt_status_text').text = f"Status: StopTask Exception for {task_id_to_stop} - {e}"
        print(f"Exception during StopTask for {task_id_to_stop}: {e}")
    finally:
        # 无论API调用成功与否，都清除本地的TaskId和WebSocket URL，防止状态不一致
        # 只有当被操作的 task_id_to_stop 与当前 ownerComp.par.Taskid 一致时才清除，
        # 避免并发操作或延迟回调导致清除了新的 TaskId
        if ownerComp.par.Taskid.eval() == task_id_to_stop:
            ownerComp.par.Taskid = "" 
            ownerComp.par.Websocketurl = ""
            print(f"Parameters for Task {task_id_to_stop} cleared after stop attempt.")
        else:
            print(f"Stop attempt for {task_id_to_stop}, but current TaskId is {ownerComp.par.Taskid.eval()}. Parameters not cleared by this call.")
        
        # 确保WebSocket最终是关闭的 (如果它对应的是已停止的task_id_to_stop的URL)
        # 这里的 ws_client 已经是关闭的，或者即将被关闭。
        current_ws_url = ownerComp.op('stt_websocket_client').par.netaddress.eval()
        # 如果当前的 WebSocket URL 属于刚停止的那个任务，并且它还 active，再次尝试关闭
        # 但通常在函数开头已经关闭了。
        # if current_ws_url == ownerComp.par.Websocketurl.eval() and ws_client.par.Active.eval():
        #    ws_client.par.Active = False

    print(f"TerminateRecognitionSession completed for TaskId: {task_id_to_stop if task_id_to_stop else 'N/A'}")