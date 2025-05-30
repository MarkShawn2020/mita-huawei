# 米塔 X 华为 - 交互式数字种子生命系统

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## 项目概述

本项目是一套完整的交互式数字种子生命系统解决方案，由米塔与华为共同开发。该系统将人机交互、声音分析、手势识别与大语言模型相结合，创造出一个动态响应的数字生命体验。

## 核心特性

- **声音分析**：实时捕捉和分析用户声音输入，转化为数字生命体的成长参数
- **手势交互**：通过摄像头捕捉用户手势，实现直觉的交互控制
- **语音转文本 (TTS)**：赋予数字生命体“发声”能力，增强互动体验
- **大语言模型集成**：利用先进的LLM技术，使数字生命体能够进行有意义的对话和反应
- **视觉呈现**：基于TouchDesigner打造的沉浸式视觉效果

## 项目结构

```
mita-huawei/
├─ .env                 # 环境变量配置
├─ .env.example         # 环境变量配置模板
├─ .env.local           # 本地环境变量配置
├─ chapter_01_voice-analysis_simple/
│   └─ mita-huawei.toe  # TouchDesigner简易声音分析项目文件
└─ chapter_02_voice-analysis/
    └─ mita-huawei.toe  # TouchDesigner完整声音分析项目文件
```

## 文档导航

项目文档已经拆分为以下几个文件，方便使用和管理：

- [项目导航](./NAVIGATION.md)：完整的章节与文档结构概览
- [开发指南](./DEVELOPMENT.md)：技术栈、安装配置与开发说明
- [使用指南](./GUIDANCE.md)：操作方法、功能介绍与故障排除

## 联系方式

- 项目维护者: [markshawn2020](https://github.com/markshawn2020)
- 项目仓库: [mita-huawei](https://github.com/markshawn2020/mita-huawei)

## 许可协议

本项目采用 MIT 许可证 - 详情请参阅 LICENSE 文件