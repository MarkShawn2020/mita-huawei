# speechModule/websocket_callbacks (Text DAT)

import json
import datetime # 确保导入

# ownerComp 指向 speechModule (因为 websocket_callbacks DAT 在 speechModule 内部)
ownerComp = me.parent() 
api_module = ownerComp.op('aliyun_api_logic').module # 获取 aliyun_api_logic 模块的引用

def onConnect(dat): # dat 是触发此回调的 WebSocket DAT (stt_websocket_client)
    """
    当 WebSocket 成功连接到阿里云服务器后调用。
    主要任务是发送 StartTranscription 指令。
    """
    print(f"{ownerComp.name} - WebSocket Client '{dat.name}': Connected to {dat.par.netaddress.eval()}")
    ownerComp.op('stt_status_text').text = "Status: STT WS Connected. Initializing session..."
    
    task_id = ownerComp.par.Taskid.eval() # 从 speechModule 的自定义参数获取 TaskId
    app_key = ownerComp.par.Appkey.eval() # 从 speechModule 的自定义参数获取 AppKey

    if not task_id:
        print(f"ERROR ({dat.name}): WebSocket connected but no TaskId found in speechModule parameters. Disconnecting.")
        ownerComp.op('stt_status_text').text = "Status: Error - WS Connected, No TaskId."
        dat.par.Active = False # 主动断开连接
        return

    # --- 构建 StartTranscription 消息 ---
    # !!! 警告: 下面的消息结构是基于通用模式的推测。 !!!
    # !!! 你必须查阅阿里云官方文档来获取确切的 JSON 结构和必需参数。!!!
    # !!! 常见的参数可能包括任务ID, app_key, 音频格式, 采样率, 是否返回中间结果等。!!!
    
    # 生成一个唯一的 message_id
    message_id = f"td_start_{task_id}_{int(datetime.datetime.now().timestamp() * 1000)}"

    start_message = {
        "header": {
            "message_id": message_id,
            "task_id": task_id,
            # "app_key": app_key, # 根据API文档，AppKey可能需要在header或payload中
            "name": "StartTranscription",       # 关键: 必须是阿里云API定义的指令名称
            "namespace": "SpeechTranscriber", # 关键: 必须是阿里云API定义的命名空间
            # "version": "1.0", # 有些API可能需要版本号
        },
        "payload": {
            # "app_key": app_key, # 或者 AppKey 在 payload 中
            "format": "PCM", # 与 create_realtime_task 中定义的Input.Format一致
            "sample_rate": 16000, # 与 create_realtime_task 中定义的Input.SampleRate一致
            "enable_intermediate_result": True, # 通常希望获取实时中间结果
            "enable_punctuation_prediction": True, # 开启标点预测
            # "enable_inverse_text_normalization": True, # 是否开启数字转阿拉伯数字等（ITN）
            # "max_sentence_silence": 800, # 句子末尾最大静默时长（毫秒），用于断句
            # "customization_id": "your_custom_model_id", # 如果使用了自学习模型
            # "vocabulary_id": "your_hotword_id", # 如果使用了热词
            # ... 其他根据API文档需要的参数 ...
        }
    }
    
    try:
        message_str = json.dumps(start_message)
        print(f"{dat.name}: Sending StartTranscription message: {message_str}")
        dat.sendText(message_str) # 通过 WebSocket DAT 发送文本消息
        ownerComp.op('stt_status_text').text = "Status: STT WS Initialized. Listening for voice..."
    except Exception as e:
        print(f"ERROR ({dat.name}): Failed to send StartTranscription message: {e}")
        ownerComp.op('stt_status_text').text = f"Status: Error Init WS - {e}"
        dat.par.Active = False # 发送初始化消息失败，断开连接
        # 也许需要通知 aliyun_api_logic 来清理HTTP任务
        # api_module.TerminateRecognitionSession() # 考虑是否需要调用
    return

def onDisconnect(dat): # dat 是触发此回调的 WebSocket DAT
    """
    当 WebSocket 连接断开时调用 (无论是主动还是被动)。
    """
    print(f"{ownerComp.name} - WebSocket Client '{dat.name}': Disconnected from {dat.par.netaddress.eval()}")
    current_status = ownerComp.op('stt_status_text').text
    
    # 避免在 TerminateRecognitionSession 过程中重复设置状态
    if "Terminat" not in current_status and "Stopping" not in current_status :
        ownerComp.op('stt_status_text').text = "Status: STT WS Disconnected."

    # 如果 Recognize 开关仍然是 ON，并且之前有 TaskID，这可能是一次意外断开。
    # 简单的处理是让用户重新触发（例如，关闭再打开 Recognize 开关）。
    # 复杂的自动重连逻辑可以后续添加。
    # if ownerComp.par.Recognize.eval() and ownerComp.par.Taskid.eval(): # Taskid可能已被Terminate过程清空
    #     print(f"WARNING ({dat.name}): Unexpected WebSocket disconnect while recognition is enabled.")
    #     # ownerComp.op('stt_status_text').text = "Status: STT WS Unexpectedly Disconnected. Please restart recognition."
    #     # 考虑是否要清除 TaskId，强制用户重新开始
    #     # ownerComp.par.Taskid = ""
    #     # ownerComp.par.Websocketurl = ""
    return

def onMessage(dat, message_str): # dat 是 WebSocket DAT, message_str 是收到的字符串
    """
    当从阿里云服务器收到 WebSocket 消息时调用。
    主要任务是解析识别结果并更新UI/状态。
    """
    # print(f"{ownerComp.name} - WebSocket Client '{dat.name}': Message Received: {message_str}")
    
    try:
        data = json.loads(message_str)

        print("onMessage: ", data)
        
        # --- 解析阿里云 STT 返回的 JSON 结构 ---
        # !!! 警告: 下面的解析逻辑是基于通用模式的推测。!!!
        # !!! 你必须仔细阅读 "实时推流" -> "获取结果" 的文档，了解确切的返回格式。!!!
        # 常见的返回消息类型:
        # 1. TranscriptionResult: 包含识别文本（中间或最终）。
        # 2. SentenceBegin / SentenceEnd: 句子开始/结束的信令。
        # 3. Error messages from server.
        # 4. Other control messages.

        header = data.get("header", {})
        payload = data.get("payload", {})
        message_name = header.get("name")
        status_code = header.get("status") # 很多API用status来表示成功或错误类型

        if status_code == 20000000: # 假设 20000000 表示成功
            if message_name == "TranscriptionResult":
                # 这是最常见的包含识别文本的消息
                result_text = payload.get("result", "") # "result" 字段通常包含文本
                # is_final = payload.get("is_final", False) # API可能用不同字段表示是否最终句
                # 阿里云文档提到 Parameters.Transcription.OutputLevel
                # 如果 OutputLevel=1 (完整句子)，收到的可能都是最终句。
                # 如果 OutputLevel=2 (中间+最终)，你需要判断。
                # 有时用消息类型或 payload 内的字段来区分，例如 sentence_end_time, duration 等。
                
                # 简化的最终句判断：如果payload里有 "sentence_end_time" 且大于0 (或其他类似标志)
                # 或者API明确给出了一个 "type" 字段表示 "intermediate" vs "final"
                is_final_sentence_segment = payload.get("status") == "SENTENCE_END" # 这是一个假设的字段

                if result_text:
                    display_text = payload.get("display_text", result_text) # 有些API会提供更适合显示的文本
                    current_display = ownerComp.op('stt_result_text').text
                    
                    # 更新UI
                    # 对于中间结果，可以替换之前的中间结果
                    # 对于最终结果，可以追加或根据sentence_id管理
                    # 简单起见，我们直接覆盖
                    ownerComp.op('stt_result_text').text = f"Recognized: {display_text}"
                    
                    status_msg_prefix = "Status: Receiving"
                    if is_final_sentence_segment: # 用你的实际判断条件替换
                        status_msg_prefix = "Status: Final segment"
                        # 将最终结果传递给中控
                        op.mainController.par.Currentstatus.val = f"Speech: {display_text}"
                    
                    ownerComp.op('stt_status_text').text = f"{status_msg_prefix}..."

            elif message_name == "SentenceBegin":
                print(f"{dat.name}: SentenceBegin event received.")
                # 可以在这里做一些UI提示或逻辑
            elif message_name == "SentenceEnd":
                print(f"{dat.name}: SentenceEnd event received.")
                # 此时 payload.get("result") 可能包含该句的最终识别文本
                final_sentence_text = payload.get("result", "")
                if final_sentence_text:
                    ownerComp.op('stt_result_text').text = f"Recognized (Final): {final_sentence_text}"
                    op.mainController.par.Currentstatus.val = f"Speech: {final_sentence_text}"
                ownerComp.op('stt_status_text').text = "Status: Sentence Ended."

            # ... 处理其他成功的消息类型 ...

        elif message_name == "TaskFailed" or (status_code and status_code != 20000000):
            # 处理服务器返回的错误消息
            error_message = payload.get("message", header.get("message", "Unknown server error"))
            print(f"ERROR ({dat.name}): Server reported an error. Status: {status_code}, Name: {message_name}, Message: {error_message}")
            ownerComp.op('stt_status_text').text = f"Status: STT Server Error - {error_message[:100]}" # 截断以防过长
            # 发生服务器端错误，通常意味着当前任务无法继续，需要终止。
            if ownerComp.par.Taskid.eval():
                print(f"Terminating session due to server-side task error: {message_name}")
                api_module.TerminateRecognitionSession()
        else:
            # 未知消息类型或未处理的成功消息
            print(f"INFO ({dat.name}): Received unhandled message type or status. Name: {message_name}, Status: {status_code}, FullMsg: {message_str[:500]}")

    except json.JSONDecodeError:
        print(f"ERROR ({dat.name}): Failed to decode JSON from WebSocket: {message_str}")
        # 这种通常不是致命错误，可能是服务器发送了非JSON的心跳或其他控制信息
    except Exception as e:
        print(f"ERROR ({dat.name}): Unexpected error processing WebSocket message: {e}. Message: {message_str}")
        ownerComp.op('stt_status_text').text = f"Status: Error proc. WS msg - {e}"
        # 严重的解析错误也可能需要终止会话
        # if ownerComp.par.Taskid.eval():
        #    api_module.TerminateRecognitionSession() 
    return

def onError(dat, error_message): # dat 是 WebSocket DAT, error_message 是连接或发送/接收层面的错误
    """
    当 WebSocket 连接本身发生错误时调用 (例如无法连接，连接被意外关闭等网络层面问题)。
    """
    print(f"{ownerComp.name} - WebSocket Client '{dat.name}': Connection Error: {error_message}")
    ownerComp.op('stt_status_text').text = f"Status: STT WS Connection Error - {error_message[:100]}"
    
    # 如果发生连接错误，并且我们认为应该有一个活动任务，则尝试终止它以清理状态。
    # 避免在 Recognize 开关关闭（即正常终止流程中）时，因为这里的错误而再次调用 Terminate。
    if ownerComp.par.Recognize.eval() and ownerComp.par.Taskid.eval():
        print(f"Terminating session due to WebSocket connection error: {error_message}")
        # 调用 TerminateRecognitionSession 会关闭WebSocket (如果还开着) 并结束HTTP任务
        api_module.TerminateRecognitionSession()
    # 如果 Recognize 本来就是OFF，或者没有 TaskId，说明可能已经是清理阶段，或者从未成功开始。
    # 在这种情况下，确保WebSocket DAT是inactive的
    elif dat.par.Active.eval():
         dat.par.Active = False
    return