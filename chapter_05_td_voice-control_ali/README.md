# 通义听悟实时语音转写 + TouchDesigner 集成方案

本项目实现了阿里云通义听悟实时语音转写API与TouchDesigner的集成，采用WebSocket桥接方式，实现实时语音转文本并在TouchDesigner中显示。

## 系统架构

系统分为两个主要部分：

1. **Python独立脚本** (`nls_demo_websocket.py`) - 负责：
   - 调用通义听悟API创建转写任务
   - 捕获麦克风音频并发送到通义听悟
   - 接收实时转写结果
   - 提供WebSocket服务器与TouchDesigner通信

2. **TouchDesigner网络** - 负责：
   - 连接到Python脚本的WebSocket服务器
   - 接收并显示实时转写结果
   - 提供用户界面管理连接

## 前置条件

- Python 3.7+
- TouchDesigner 2021+
- 阿里云账号与通义听悟服务开通
- 安装所需Python依赖

## 安装依赖

```bash
pip install websockets dotenv python-dotenv pyaudio aliyun-python-sdk-core aliyun-python-sdk-tingwu
```

## 配置步骤

1. 在项目根目录创建 `.env` 文件，添加以下内容：

```
ALIBABA_CLOUD_ACCESS_KEY_ID=你的阿里云AccessKey
ALIBABA_CLOUD_ACCESS_KEY_SECRET=你的阿里云AccessKeySecret
TINGWU_APP_KEY=你的通义听悟AppKey
```

## 运行方法

### 1. 启动Python脚本

```bash
cd /path/to/project
python src/nls_demo_websocket.py
```

参数说明:
- `--ws-host`: WebSocket服务器主机 (默认: 127.0.0.1)
- `--ws-port`: WebSocket服务器端口 (默认: 8765)
- `--duration`: 录制时长，0表示无限录制 (默认: 0)
- `--sample-rate`: 音频采样率 (默认: 16000)
- `--language`: 源语言 (默认: cn)
- `--enable-translation`: 启用翻译
- `--target-language`: 目标翻译语言 (默认: en)

例如，启动10秒的录制并开启英文翻译:

```bash
python src/nls_demo_websocket.py --duration 10 --enable-translation --target-language en
```

### 2. 在TouchDesigner中构建网络

在TouchDesigner中，需要创建以下组件构成一个基础网络:

1. **WebSocket DAT**
   - 设置连接地址为 `ws://127.0.0.1:8765` (或自定义的主机和端口)
   - 设置回调函数处理接收到的消息

2. **Text DAT**
   - 用于显示转写结果

3. **控制面板**
   - 包含连接/断开按钮
   - 状态显示
   - 日志记录

4. **Container COMP**
   - 加载 `tingwu_receiver.py` 脚本提供WebSocket管理功能

## TouchDesigner网络构建步骤

1. 创建新的TouchDesigner项目
2. 添加一个Container COMP，重命名为 `tingwu_receiver`
3. 在Container内添加以下组件:
   - WebSocket DAT (命名为 `websocket1`)
   - Text DAT (命名为 `text_display`)
   - Text DAT (命名为 `connection_status`)
   - Table DAT (命名为 `log`)
   - Button COMP (命名为 `connect_button`)
   - Button COMP (命名为 `disconnect_button`)
   - Field COMP (命名为 `host_field`，默认值为 `127.0.0.1`)
   - Field COMP (命名为 `port_field`，默认值为 `8765`)
4. 将 `tingwu_receiver.py` 脚本内容粘贴到Container的扩展部分

5. 在WebSocket DAT上设置以下回调:
   - onConnect: `parent().onWSConnect()`
   - onDisconnect: `parent().onWSDisconnect()`
   - onMessage: `parent().onWSMessage(msg)`

6. 在按钮上设置回调:
   - connect_button onClick: `parent().connect()`
   - disconnect_button onClick: `parent().disconnect()`

## 实现原理

系统工作流程:

1. Python脚本启动，初始化通义听悟SDK并创建WebSocket服务器
2. TouchDesigner连接到WebSocket服务器
3. Python脚本捕获麦克风音频，发送到通义听悟服务
4. 通义听悟返回实时转写结果给Python脚本
5. Python脚本通过WebSocket将结果转发给TouchDesigner
6. TouchDesigner接收结果并更新显示

## 注意事项

- 确保防火墙允许WebSocket通信
- 通义听悟服务有调用频率和额度限制，请参考官方文档
- 音频设置需与通义听悟要求匹配 (PCM格式, 16kHz采样率, 16bit位深, 单声道)

## 故障排除

- WebSocket连接失败:
  - 检查Python脚本是否正在运行
  - 检查主机和端口设置
  - 检查网络连接和防火墙设置

- 音频捕获问题:
  - 检查麦克风权限
  - 检查音频设备是否被其他应用占用

- 通义听悟API连接问题:
  - 检查API密钥是否正确
  - 检查网络连接
  - 检查服务是否可用
