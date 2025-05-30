# 米塔 X 华为 - 交互式数字种子生命系统

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## 项目概述

本项目是一套完整的交互式数字种子生命系统解决方案，由米塔与华为共同开发。该系统将人机交互、声音分析、手势识别与大语言模型相结合，创造出一个动态响应的数字生命体验。

## 核心特性

- **声音分析**：实时捕捉和分析用户声音输入，转化为数字生命体的成长参数
- **手势交互**：通过摄像头捕捉用户手势，实现直观的交互控制
- **语音转文本 (TTS)**：赋予数字生命体"发声"能力，增强互动体验
- **大语言模型集成**：利用先进的LLM技术，使数字生命体能够进行有意义的对话和反应
- **视觉呈现**：基于TouchDesigner打造的沉浸式视觉效果

## 技术栈

- **Python**：核心逻辑和数据处理
- **TouchDesigner**：视觉设计和实时渲染
- **大语言模型 (LLM)**：智能对话和内容生成
- **计算机视觉**：手势识别和交互跟踪
- **音频处理**：声音分析和合成技术
- **阿里云服务**：用于部署和扩展系统功能

## 项目结构

```
mita-huawei/
├── .env                 # 环境变量配置
├── .env.example         # 环境变量配置模板
├── .env.local           # 本地环境变量配置
├── chapter_01_voice-analysis_simple/
│   └── mita-huawei.toe  # TouchDesigner简易声音分析项目文件
└── chapter_02_voice-analysis/
    └── mita-huawei.toe  # TouchDesigner完整声音分析项目文件
```

## 安装与配置

### 系统要求

- Python 3.8+
- TouchDesigner 2022+ (商业或非商业版)
- 摄像头和麦克风设备

### 环境配置

1. 克隆仓库：
   ```bash
   git clone https://github.com/markshawn2020/mita-huawei.git
   cd mita-huawei
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 配置环境变量：
   - 复制 `.env.example` 到 `.env` 并填写必要的配置信息
   - 对于本地开发，可以使用 `.env.local` 覆盖默认配置
   - 确保配置阿里云服务所需的密钥：
     ```
     ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
     ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
     ```

## 使用指南

1. 使用TouchDesigner打开相应章节的 `.toe` 文件
2. 确保相机和麦克风设备已连接并正确配置
3. 运行项目，开始体验交互式数字种子生命

### 简易声音分析 (chapter_01)

适合初学者了解系统基本原理，只包含声音输入分析与基础视觉反馈。

### 完整声音分析 (chapter_02)

包含更复杂的声音处理算法，以及更丰富的视觉效果和交互方式。

## 开发与扩展

本项目采用模块化设计，可以根据需求扩展新功能：

- 添加新的手势识别模式
- 集成不同的LLM模型
- 自定义视觉效果和互动方式

## 云服务集成

本项目整合了多种云服务，提供更强大的功能支持：

### 阿里云服务

本项目利用阿里云的多项服务实现核心功能：

- **语音识别与合成（智能语音交互）**：实现语音指令处理与文本转语音功能
- **实时计算（函数计算）**：处理复杂的响应逻辑和数据分析
- **对象存储（OSS）**：存储用户生成的数字生命数据和媒体资源

### 环境变量配置

为了正常访问云服务，需要在 `.env` 文件中配置以下关键参数：

```
# 阿里云认证

ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id            # 阿里云访问密钥ID
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret    # 阿里云访问密钥密钥

# 其他可选配置

ALIBABA_CLOUD_REGION=cn-hangzhou                          # 区域设置
ALIBABA_CLOUD_OSS_BUCKET=your-bucket-name                 # OSS存储桶名称
```

注意：请勿将包含密钥的配置文件添加到版本控制中，确保项目安全。

## 故障排除

- 如遇设备连接问题，请检查系统设备管理器中相机和麦克风是否被正确识别
- TouchDesigner文件加载失败时，请确认软件版本兼容性
- 云服务访问失败时，请检查环境变量配置和网络连接

## 联系方式

- 项目维护者: [markshawn2020](https://github.com/markshawn2020)
- 项目仓库: [mita-huawei](https://github.com/markshawn2020/mita-huawei)

## 许可协议

本项目采用 MIT 许可证 - 详情请参阅 LICENSE 文件
