# VideoWhisper - 视频智语 🎥✨

一个智能的视频转文本处理系统，支持视频下载、语音转录、智能摘要和内容分析。

## ✨ 功能特性

- 🎬 **多平台支持**: YouTube、抖音等主流视频平台
- 🗣️ **智能语音识别**: 基于SiliconFlow的高精度语音转文本
- 🤖 **AI内容分析**: 使用OpenAI/Gemini进行智能摘要和内容分析
- 📋 **任务管理**: 支持任务历史记录和进度追踪
- 💾 **数据持久化**: 自动保存处理结果和任务历史
- 🌐 **Web界面**: 简洁易用的Web操作界面
- 📊 **实时进度**: 可视化处理进度追踪
- 📁 **文件管理**: 支持结果下载和历史查看

## 🛠️ 技术栈

- **后端**: Python Flask
- **语音识别**: SiliconFlow API
- **AI处理**: OpenAI/Gemini API
- **视频处理**: yt-dlp + FFmpeg
- **前端**: Bootstrap 5 + Vanilla JavaScript

## 📋 系统要求

- Python 3.7+
- FFmpeg
- 网络连接（用于API调用）

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/VideoWhisper.git
cd VideoWhisper
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 安装FFmpeg

**Windows用户**:
```bash
# 使用提供的PowerShell脚本
powershell -ExecutionPolicy Bypass -File install-ffmpeg.ps1
```

**Linux用户**:
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS用户**:
```bash
brew install ffmpeg
```

### 4. 配置API密钥

编辑 `config.yaml` 文件，填入你的API密钥：

```yaml
apis:
  siliconflow:
    api_key: "your_siliconflow_api_key"
  openai:
    api_key: "your_openai_api_key"
  gemini:
    api_key: "your_gemini_api_key"
```

### 5. 运行应用

```bash
python run.py
```

访问 http://localhost:5000 开始使用！

## 📖 使用指南

### 基础使用

1. **输入视频URL**: 支持YouTube、抖音等平台链接
2. **选择AI模型**: OpenAI或Gemini
3. **开始处理**: 系统自动完成视频下载→语音提取→文本转录→智能分析
4. **查看结果**: 获取逐字稿、摘要报告和内容分析
5. **下载文件**: 支持下载处理结果

### 抖音视频支持

抖音视频需要Cookie认证：

1. 浏览器访问 https://www.douyin.com 并登录
2. 使用浏览器扩展导出cookies
3. 将cookies保存为项目根目录下的 `cookies.txt`

## 📁 项目结构

```
VideoWhisper/
├── app/                    # 应用主目录
│   ├── services/          # 核心服务
│   │   ├── video_downloader.py
│   │   ├── audio_extractor.py
│   │   ├── speech_to_text.py
│   │   ├── text_processor.py
│   │   └── video_processor.py
│   ├── models/            # 数据模型
│   ├── config/            # 配置管理
│   └── main.py           # 路由处理
├── web/                   # 前端资源
│   ├── static/
│   └── templates/
├── config.yaml           # 主配置文件
├── requirements.txt      # Python依赖
└── run.py               # 启动脚本
```

## 🔧 配置说明

### config.yaml 详细配置

```yaml
# API配置
apis:
  siliconflow:          # 语音识别服务
    base_url: "https://api.siliconflow.cn/v1"
    api_key: "your_key"
    model: "FunAudioLLM/SenseVoiceSmall"
  
  openai:               # OpenAI服务
    api_key: "your_key"
    model: "gpt-3.5-turbo"
  
  gemini:               # Gemini服务
    api_key: "your_key"
    model: "gemini-pro"

# 系统配置
system:
  temp_dir: "./temp"        # 临时文件目录
  output_dir: "./output"    # 输出文件目录
  max_file_size: 500        # 最大文件大小(MB)

# 下载器配置
downloader:
  douyin:
    enabled: true
    cookies_file: "./cookies.txt"
```

## 📄 输出文件

每个处理任务会生成以下文件：

- `transcript.txt` - 格式化逐字稿
- `transcript_with_timestamps.txt` - 带时间戳的逐字稿
- `summary.md` - 总结报告（Markdown格式）
- `data.json` - 完整处理数据（JSON格式）

## 🧪 测试

```bash
# 简单功能测试
python test_simple.py

# 完整集成测试
python test_complete.py

# 基础测试
python test.py
```

## 🤝 贡献指南

1. Fork 本项目
2. 创建特性分支: `git checkout -b feature/AmazingFeature`
3. 提交更改: `git commit -m 'Add some AmazingFeature'`
4. 推送分支: `git push origin feature/AmazingFeature`
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证

## ⭐ 支持项目

如果这个项目对你有帮助，请给它一个星标！

## 📧 联系方式

- 项目链接: https://github.com/yourusername/VideoWhisper
- 问题反馈: https://github.com/yourusername/VideoWhisper/issues

## 🎯 未来计划

- [ ] 支持更多视频平台
- [ ] 批量处理功能
- [ ] 多语言支持
- [ ] API接口开放
- [ ] 移动端适配

---

**VideoWhisper** - 让视频内容触手可及 ✨