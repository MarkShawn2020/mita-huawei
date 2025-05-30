# 米塔 X 华为 - 开发指南

## 技术栈

- **Python**：核心逻辑和数据处理
- **TouchDesigner**：视觉设计和实时渲染
- **大语言模型 (LLM)**：智能对话和内容生成
- **计算机视觉**：手势识别和交互跟踪
- **音频处理**：声音分析和合成技术
- **阿里云服务**：用于部署和扩展系统功能

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