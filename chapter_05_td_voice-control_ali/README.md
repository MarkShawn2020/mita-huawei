# 通义听悟实时语音转写 + TouchDesigner 集成方案

本项目实现了阿里云通义听悟实时语音转写API与TouchDesigner的集成，采用WebSocket桥接方式，实现实时语音转文本并在TouchDesigner中显示。

## 系统架构

系统分为两个主要部分：

1.  **Python独立脚本 (`src/nls_demo.py`)** - 负责：
    *   调用通义听悟API创建转写任务。
    *   捕获麦克风音频并发送到通义听悟服务。
    *   接收实时转写结果。
    *   内置一个WebSocket服务器，用于与TouchDesigner进行实时通信。

2.  **TouchDesigner网络** - 负责：
    *   通过 `WebSocket DAT` 连接到Python脚本的WebSocket服务器。
    *   通过 `DAT Execute DAT` 处理接收到的消息。
    *   通过 `Text DAT` 显示实时转写结果。

## 前置条件

*   Python 3.7+ (建议3.8或更高版本，以良好支持 `asyncio` 和 `websockets`)
*   TouchDesigner (版本应支持 `WebSocket DAT` 和Python 3.7+ scripting)
*   阿里云账号，并已开通通义听悟服务。
*   有效的阿里云AccessKey ID, AccessKey Secret, 以及通义听悟AppKey。

## 安装依赖

在您的Python环境中，安装必要的库。项目根目录下通常包含 `requirements.txt`，可以使用：

```bash
pip install -r requirements.txt 
```

如果 `requirements.txt` 不完整或未提供，主要依赖包括：

```bash
pip install websockets python-dotenv pyaudio aliyun-python-sdk-core aliyun-python-sdk-tingwu nls Pillow # Pillow可能用于其他demo，但核心转写不需要
```

(确保 `nls` Python SDK 来自阿里云官方或可靠来源，通常随 `aliyun-python-sdk-tingwu` 一起安装或需要单独处理)。

## 配置步骤

1.  在项目根目录 (`mita-huawei`) 下创建或确认 `.env` 文件存在。如果您的 `nls_demo.py` 脚本位于 `src` 子目录，它通常会配置为从父目录加载 `.env` 文件。
    示例 `.env` 内容：

    ```env
    ALIBABA_CLOUD_ACCESS_KEY_ID="YOUR_ACCESS_KEY_ID"
    ALIBABA_CLOUD_ACCESS_KEY_SECRET="YOUR_ACCESS_KEY_SECRET"
    TINGWU_APP_KEY="YOUR_TINGWU_APP_KEY"
    ```
    将引号内的占位符替换为您的实际凭据。

## 运行方法

### 1. 启动Python实时转写脚本

打开终端，导航到 `src` 目录，然后运行 `nls_demo.py`：

```bash
cd /path/to/mita-huawei/chapter_05_td_voice-control_ali/src
python nls_demo.py
```

脚本将尝试从 `.env` 文件加载凭据。如果凭据未在 `.env` 中配置或加载失败，您可能需要通过命令行参数传递它们：

```bash
python nls_demo.py --app-key YOUR_APP_KEY --access-key-id YOUR_ACCESS_KEY_ID --access-key-secret YOUR_ACCESS_KEY_SECRET
```

**脚本参数 (部分主要):**
*   `--access-key-id`: 阿里云 Access Key ID (优先于 `.env`)
*   `--access-key-secret`: 阿里云 Access Key Secret (优先于 `.env`)
*   `--app-key`: 通义听悟 App Key (优先于 `.env`)
*   `--language`: 源语言 (默认: `cn`)
*   `--sample-rate`: 音频采样率 (默认: `16000` Hz)
*   `--duration`: 录制时长 (秒)。脚本目前可能在固定时长后停止或需要手动停止 (Ctrl+C)。

成功启动后，Python脚本会开始监听麦克风，并启动一个WebSocket服务器。默认情况下，此服务器监听 `ws://127.0.0.1:8765`。

### 2. TouchDesigner设置

在TouchDesigner中，构建以下网络：

1.  **WebSocket DAT**:
    *   将其 `Active` 参数设置为 On。
    *   **Network Address**: `ws://127.0.0.1:8765` (确保这与Python脚本中 `WEBSOCKET_HOST` 和 `WEBSOCKET_PORT` 的设置一致)。

2.  **Text DAT**:
    *   创建一个Text DAT，用于显示转写结果。可以将其命名为 `transcription_display`。

3.  **DAT Execute DAT**:
    *   将其 `DAT` 参数指向您创建的 `WebSocket DAT` (例如，如果WebSocket DAT名为 `websocket1`, 则指向 `op('websocket1')`)。
    *   启用以下回调，并在脚本区域粘贴相应的Python代码：
        *   `onConnect`
        *   `onDisconnect`
        *   `onReceiveText`

    **DAT Execute DAT 脚本示例:**
    ```python
    # me - this DAT
    # dat - the WebSocket DAT that this DAT Execute is monitoring

    def onConnect(dat):
        print(f"TD: WebSocket connected to {dat.par.address.eval()}")
        # Optional: Clear previous text or show a connected message
        # op('transcription_display').text = "Connected. Listening..."
        return

    def onDisconnect(dat):
        print(f"TD: WebSocket disconnected from {dat.par.address.eval()}")
        # Optional: Show a disconnected message
        # op('transcription_display').text = "Disconnected."
        return

    def onReceiveText(dat, rowIndex, message):
        # 'dat' is the WebSocket DAT that received the message
        # 'message' is the received string
        display_op = op('transcription_display') # Ensure this path is correct

        if message == "__TRANSCRIBE_COMPLETED__":
            # Handle transcription completion if needed
            print("TD: Transcription completed signal received.")
            # display_op.text += "\n--- Transcription Completed ---"
        elif message.startswith("Connection test:"):
            # Handle the initial test message from the Python script
            print(f"TD: Received test message: {message}")
            # display_op.text = message # Or append, or ignore in final display
        else:
            # Update the Text DAT with the live transcription
            display_op.text = message 
        return
    ```

## 实现原理

1.  Python脚本 (`nls_demo.py`) 启动后，初始化通义听悟SDK，配置音频捕获，并启动一个WebSocket服务器 (默认 `ws://127.0.0.1:8765`)。
2.  TouchDesigner中的 `WebSocket DAT` 连接到此服务器。
3.  当Python脚本通过麦克风捕获音频并从通义听悟服务获得转写结果时，它会将这些文本数据通过WebSocket连接发送给所有连接的客户端 (即TouchDesigner)。
4.  TouchDesigner的 `WebSocket DAT` 接收到文本消息，触发 `DAT Execute DAT` 中的 `onReceiveText` 回调。
5.  该回调脚本将接收到的文本更新到 `Text DAT` (`transcription_display`) 中，从而在TouchDesigner界面上实时显示语音转写内容。

## 注意事项

*   **防火墙**: 确保您的系统防火墙没有阻止Python脚本监听端口或TouchDesigner连接到该端口。对于本地 `127.0.0.1` 连接，这通常不是问题。
*   **凭据安全**: 避免在脚本中硬编码API密钥。使用 `.env` 文件是推荐的做法。
*   **API限制**: 注意阿里云通义听悟服务的API调用频率和时长限制。
*   **Python环境**: 确保TouchDesigner使用的Python环境与运行独立脚本的环境兼容，或两者都能访问所需的库（尽管在此桥接方案中，TD主要只使用内置的WebSocket功能）。
*   **Error Handling**: Python脚本和TouchDesigner回调脚本都应包含适当的错误处理和日志记录，以便于调试。

## 故障排除

*   **TouchDesigner未连接/未收到消息**:
    *   **检查Python脚本**: 确保 `nls_demo.py` 正在运行且没有错误。查看其控制台输出是否有WebSocket服务器启动成功的日志 (e.g., `INFO ... Starting WebSocket server ...` or `INFO ... WebSocket server (async with) is running ...`) 和客户端连接日志 (e.g., `INFO ... TouchDesigner client connected ...`)。
    *   **检查TD WebSocket DAT**: 确认 `Network Address` 完全正确。查看DAT节点本身是否有错误指示器。检查TouchDesigner的Textport (Alt+T) 是否有连接错误或脚本错误。
    *   **Test Message**: `nls_demo.py` (在之前的修改中) 会在连接成功时发送一个测试消息。确认这个测试消息是否在TD的 `onReceiveText` 中被接收和打印。
*   **音频问题 (Python脚本端)**:
    *   检查系统麦克风是否被正确选择和授权。
    *   Python脚本控制台是否有音频捕获相关的错误。
*   **转写无结果 (但连接正常)**:
    *   Python脚本控制台是否有通义听悟API相关的错误或警告。
    *   确认您正在对着麦克风说话，并且环境噪音不要过大。
    *   检查 `on_result` 回调在Python脚本中是否被触发，以及 `send_to_td` 是否被调用。可用
