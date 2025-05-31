# speechModule/vad_callbacks (Text DAT)

# ownerComp 指向 speechModule Base COMP
ownerComp = me.parent() 

# --- Operator References (确保这些路径在你的 speechModule 中是正确的) ---
# API逻辑模块
api_module = ownerComp.op('aliyun_api_logic').module
# 包含待发送音频数据的 CHOP to DAT
audio_chunk_dat = ownerComp.op('CHOP_To_DAT1') # 修改为你的 CHOP to DAT 名称
# WebSocket客户端
ws_client = ownerComp.op('stt_websocket_client')
# Timer CHOP 用于定期发送音频
timer_send_audio = ownerComp.op('timer_send_audio') # 修改为你的 Timer CHOP 名称
# VAD 信号 CHOP (通常是 Logic CHOP 或 Threshold CHOP 的输出)
vad_signal_chop = ownerComp.op('vad_active') # 修改为你的 VAD CHOP 名称 (例如 'logic1')
# 状态显示 Text DAT
status_display_dat = ownerComp.op('stt_status_text')

# --- VAD Event Callbacks (由 CHOP Execute DAT 调用) ---

def onOffToOn(channel, sampleIndex, val, prev):
    """用户开始说话 (VAD 从 0 变为 1)"""
    print(f"{ownerComp.name} - VAD: Voice Detected (OnOffToOn).")
    status_display_dat.text = "Status: VAD On - Processing..."
    
    # 检查总使能开关 (speechModule.par.Recognize) 是否打开
    if not ownerComp.par.Recognize.eval():
        print(f"{ownerComp.name} - VAD: Recognition is disabled. Ignoring VAD event.")
        status_display_dat.text = "Status: VAD On - Reco Disabled."
        return

    # Always call EnsureRecognitionSessionActive. 
    # It will handle reuse if TaskId exists, or create a new one if not.
    if api_module.EnsureRecognitionSessionActive():
        # If EnsureRecognitionSessionActive returns True, it means either a new session is creating 
        # or an existing one is being reused and the WebSocket is being activated.
        # The status text will be updated by EnsureRecognitionSessionActive or websocket_callbacks.
        pass # Further status updates will come from aliyun_api_logic or websocket_callbacks
    else:
        # EnsureRecognitionSessionActive returned False, indicating a failure in creating/reusing.
        status_display_dat.text = "Status: VAD On - Session Init Failed."
        print(f"{ownerComp.name} - VAD: Failed to ensure recognition session is active.")

    # 确保 Timer CHOP (timer_send_audio) 是激活的，以便开始/继续发送音频块
    # SendAudioChunk 内部会再次检查所有条件
    # if not timer_send_audio.par.Active.eval():
    #      timer_send_audio.par.Active = True
    # 如果Timer是segment模式并且已经结束了一轮，可以pulse一下start确保它从头开始
    # 或者如果Timer是持续运行的，确保它的逻辑能正确处理VAD信号
    # 对于持续运行的Timer，这里不需要特别操作，SendAudioChunk会判断
    
    return


def onOnToOff(channel, sampleIndex, val, prev):
    """用户说话结束 (VAD 从 1 变为 0)"""
    print(f"{ownerComp.name} - VAD: Voice Ended (OnToOff).")
    status_display_dat.text = "Status: VAD Off - Audio Paused."
    return


def whileOn(channel, sampleIndex, val, prev):
    """当VAD信号持续为1时，每帧调用 (通常不需要太多逻辑在这里)"""
    # print(f"VAD Active: {val}") # 非常频繁的打印，仅调试用
    # 主要的音频发送逻辑由 Timer CHOP (timer_send_audio) 驱动
    return

# --- Timer CHOP Callback (由 timer_send_audio 调用) ---

def SendAudioChunk(timerOp): # timerOp 是调用此函数的 Timer CHOP (timer_send_audio)
    """由 Timer CHOP 定期调用，用于发送音频数据块到阿里云"""

    # 详细检查所有条件是否满足发送音频的要求
    can_send = True
    reason = ""

    if not ownerComp.par.Recognize.eval():
        can_send = False
        reason = "Recognition globally disabled."
    elif not ownerComp.par.Taskid.eval():
        can_send = False
        reason = "No active Aliyun TaskId."
    elif vad_signal_chop.numSamples == 0 or vad_signal_chop.vals[0] == 0: # 检查VAD信号
        can_send = False
        reason = "VAD signal is off (no voice detected)."
    
    if not can_send:
        # if reason: print(f"SendAudioChunk: Not sending audio - {reason}")
        # 如果VAD信号关闭，可以考虑在此处禁用Timer，以节省资源，
        # 并在onOffToOn中重新启用它。但如果Timer一直运行，这里的判断也足够。
        # if not (vad_signal_chop.numSamples > 0 and vad_signal_chop.vals[0] > 0) and timerOp.par.Active.eval():
        #    timerOp.par.Active = False # 例如，没说话就关掉timer
        return

    # 获取并转换音频数据
    # 确保 audio_chunk_dat (CHOP to DAT) 的配置是合适的，
    # 例如，它应该只包含自上次发送以来的新音频数据。
    # 一个简单的策略是，CHOP to DAT 的 "Clear Output" 参数可以设置为 "On Update"，
    # 并且它的更新由一个与 Timer CHOP 同步的机制触发，或者它捕获固定长度的音频。
    # 如果 CHOP to DAT 是累积式的，你需要实现逻辑来只发送新的部分。
    # 这里假设 audio_chunk_dat 在被调用时包含了“当前”要发送的块。
    
    if not audio_chunk_dat or audio_chunk_dat.numRows == 0:
        # print("SendAudioChunk: No audio data in audio_chunk_dat.")
        return

    pcm_bytes = api_module.convert_float_to_pcm16_bytes(audio_chunk_dat)
    
    if pcm_bytes:
        # print(f"SendAudioChunk: Sending {len(pcm_bytes)} bytes of audio data.")
        try:
            ws_client.sendBytes(pcm_bytes)
            # status_display_dat.text = f"Status: Sending Audio ({len(pcm_bytes)}B)" # 频繁更新，可选
        except Exception as e:
            print(f"{ownerComp.name} - SendAudioChunk: Error sending bytes via WebSocket: {e}")
            status_display_dat.text = f"Status: WS Send Error - {e}"
            # 发生发送错误可能意味着WebSocket连接有问题，可能需要重置或终止会话
            # 例如: api_module.TerminateRecognitionSession() # 严重错误时
            # 或者，更温和地尝试重新连接:
            # ws_client.par.Active = False
            # td.run(f"op('{ws_client.path}').par.Active = True", delayFrames=60) # 延迟尝试重连
    # else:
        # print("SendAudioChunk: PCM bytes conversion resulted in empty data.")

    # 如果你的 CHOP to DAT 是“一次性”的（例如，Audio Record CHOP 录制固定长度，然后送入），
    # 你可能需要在这里清除它，或者重新触发录制。
    # audio_chunk_dat.clear() # 如果需要清除
    # op('your_audio_record_chop').par.record = 0
    # op('your_audio_record_chop').par.record = 1 
    return