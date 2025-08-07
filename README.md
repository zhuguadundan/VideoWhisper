# VideoWhisper - 视频智语 🎥✨

> 当前版本：v0.1 | 最后更新：2025-08-07

一个智能的视频转文本处理系统，支持视频下载、语音转录、智能摘要和内容分析。

## ✨ 功能特性

- 🎬 **多平台支持**: YouTube等主流视频平台
- 🗣️ **智能语音识别**: 基于SiliconFlow的高精度语音转文本
- 🤖 **AI内容分析**: 使用OpenAI/Gemini进行智能摘要和内容分析
- 📋 **任务管理**: 支持任务历史记录和进度追踪
- 💾 **数据持久化**: 自动保存处理结果和任务历史
- 🌐 **Web界面**: 简洁易用的Web操作界面
- 📊 **实时进度**: 可视化处理进度追踪
- 📁 **文件管理**: 完整的文件管理系统，支持批量操作
- 🔍 **智能搜索**: 快速定位和管理所有文件
- 🛡️ **安全删除**: 支持单个文件和整个任务的安全删除
- ⚙️ **在线配置**: Web界面直接配置API密钥和系统设置

## 📈 版本更新日志

### v2.1.1 (2025-08-07) - 任务管理优化 🔄

**🔧 系统优化:**
- ✅ **智能任务清理** - 程序重启后自动处理未完成任务
- ✅ **任务状态管理** - 防止程序异常退出导致的任务状态异常
- ✅ **重启安全机制** - 确保系统重启后不会继续执行中断的任务
- ✅ **错误恢复能力** - 未完成任务自动标记为失败状态

**🛡️ 稳定性增强:**
- ✅ 消除任务状态不一致问题
- ✅ 提高系统重启后的可靠性
- ✅ 优化任务持久化机制

### v2.1.0 (2025-08-07) - 文件管理系统重大更新 🚀

**🆕 新增功能:**
- ✅ **完整文件管理界面** - 全新的文件管理页面，支持所有文件类型
- ✅ **统计面板** - 实时显示文件数量、总大小、分类统计
- ✅ **智能搜索** - 按文件名、任务标题、文件描述搜索
- ✅ **批量操作** - 支持多选、批量下载、批量删除
- ✅ **文件分类** - 自动识别视频、音频、文本、数据等文件类型
- ✅ **任务管理** - 可删除整个任务的所有相关文件
- ✅ **响应式设计** - 完美适配桌面端和移动端
- ✅ **Web设置界面** - 在线配置API密钥和系统参数
- ✅ **Gemini Base URL支持** - 支持自定义Gemini API地址

**🔧 API增强:**
- ✅ `GET /api/files` - 获取所有文件列表
- ✅ `GET /api/files/download/<file_id>` - 统一文件下载接口
- ✅ `POST /api/files/delete` - 批量删除文件
- ✅ `POST /api/files/delete-task/<task_id>` - 删除任务所有文件
- ✅ `POST /api/settings` - 在线更新配置
- ✅ `GET /api/settings` - 获取当前配置

**🎨 界面优化:**
- ✅ 添加文件管理导航链接到所有页面
- ✅ 现代化玻璃拟态设计风格
- ✅ 彩色文件类型图标和标识
- ✅ 操作确认弹窗和实时反馈
- ✅ 设置页面新增Gemini Base URL配置项

**🛡️ 安全增强:**
- ✅ 重要操作二次确认机制
- ✅ 路径遍历攻击防护
- ✅ 详细的操作日志和错误反馈
- ✅ 配置参数验证和安全存储

### v2.0.0 (2025-01-01) - 系统架构重构
**🔄 重大重构:**
- ✅ 完全重写核心处理引擎
- ✅ 基于Flask的Web应用架构
- ✅ 模块化服务设计
- ✅ 数据模型标准化

**🆕 核心功能:**
- ✅ YouTube视频下载支持
- ✅ SiliconFlow语音识别集成
- ✅ OpenAI/Gemini双AI引擎支持
- ✅ 任务队列和进度追踪
- ✅ 数据持久化存储

**🎨 用户界面:**
- ✅ Bootstrap 5响应式设计
- ✅ 实时进度显示
- ✅ 任务历史记录
- ✅ 文件下载管理

### v1.2.0 (2024-12-15) - AI功能增强
- ✅ 新增Gemini AI支持
- ✅ 智能内容分析和摘要
- ✅ 多种输出格式 (TXT, MD, JSON)
- ✅ 时间戳精确对齐

### v1.1.0 (2024-12-01) - 功能增强
- ✅ 批量音频处理
- ✅ 错误恢复机制
- ✅ 平台支持优化

### v1.0.0 (2024-11-15) - 首次发布
- ✅ YouTube视频下载
- ✅ FFmpeg音频提取
- ✅ 基础语音转文本
- ✅ 命令行界面

## 🛠️ 技术栈

- **后端**: Python Flask 2.3.3
- **语音识别**: SiliconFlow API (FunAudioLLM/SenseVoiceSmall)
- **AI处理**: OpenAI GPT-4 / Google Gemini Pro
- **视频处理**: yt-dlp + FFmpeg
- **前端**: Bootstrap 5 + Vanilla JavaScript
- **数据存储**: JSON文件 + YAML配置

## 📋 系统要求

- Python 3.7+
- FFmpeg (自动安装脚本提供)
- 4GB+ 可用磁盘空间
- 网络连接（用于API调用）

## 🚀 快速开始

### 方式一：Docker部署（推荐） 🐳

Docker部署是最简单快速的方式，无需手动安装依赖：

```bash
# 1. 克隆项目
git clone https://github.com/zhuguadundan/VideoWhisper.git
cd VideoWhisper

# 2. 构建和启动（Windows）
build-docker.bat

# 构建和启动（Linux/Mac）
chmod +x build-docker.sh
./build-docker.sh

# 3. 使用Docker Compose启动
docker-compose up -d

# 4. 访问应用
# http://localhost:5000
```

详细的Docker部署指南请查看 [DOCKER.md](DOCKER.md)

### 方式二：传统部署

#### 1. 克隆项目

```bash
git clone https://github.com/zhuguadundan/VideoWhisper.git
cd VideoWhisper
```

#### 2. 安装依赖

```bash
pip install -r requirements.txt
```

#### 3. 安装FFmpeg

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

#### 4. 配置API密钥

有两种配置方式：

**方式一：Web界面配置（推荐）**
1. 运行程序：`python run.py`
2. 访问 http://localhost:5000
3. 点击"设置"页面配置API密钥

**方式二：手动编辑配置文件**
编辑 `config.yaml` 文件：

```yaml
apis:
  siliconflow:
    api_key: "your_siliconflow_api_key"
    base_url: "https://api.siliconflow.cn/v1"
  openai:
    api_key: "your_openai_api_key"
  gemini:
    api_key: "your_gemini_api_key"
    base_url: "https://generativelanguage.googleapis.com/v1"
```

#### 5. 运行应用

```bash
python run.py
```

访问 http://localhost:5000 开始使用！

## 📖 使用指南

### 🎬 视频处理流程

1. **输入视频URL**: 支持YouTube、抖音等平台链接
2. **选择AI模型**: OpenAI GPT-4 或 Google Gemini Pro
3. **开始处理**: 系统自动完成完整处理流程：
   - 📥 视频下载
   - 🎵 音频提取 
   - 📝 语音转文本
   - 🧠 AI智能分析
   - 📊 生成报告
4. **查看结果**: 获取多种格式的处理结果

### 📁 文件管理 (v2.1.0核心功能)

**统计概览**
- 📊 实时文件统计面板
- 📈 按类型分类统计
- 💾 总存储空间占用

**智能搜索**
- 🔍 按文件名搜索
- 🏷️ 按任务标题搜索
- 📝 按文件描述搜索

**批量操作**
- ☑️ 全选/清空选择
- 📦 批量下载多个文件
- 🗑️ 批量删除文件
- 📋 任务级删除（删除整个任务）

**支持的文件类型**
- 📹 **视频**: .mp4, .avi, .mov, .mkv, .webm
- 🎵 **音频**: .mp3, .wav, .aac, .m4a, .ogg
- 📝 **文本**: .txt (逐字稿)
- 📊 **报告**: .md (智能摘要)
- 💾 **数据**: .json (处理数据)

### ⚙️ 在线设置 (v2.1.0新功能)

**API配置**
- 🔑 SiliconFlow API密钥配置
- 🤖 OpenAI API密钥配置
- 🧠 Gemini API密钥和Base URL配置
- ✅ 连接测试功能

**系统设置**
- 📁 文件存储路径配置
- ⚡ 处理超时设置
- 🔒 安全参数调整

## 📁 项目结构

```
VideoWhisper/
├── app/                    # 应用主目录
│   ├── services/          # 核心服务层
│   │   ├── video_downloader.py    # 视频下载服务
│   │   ├── audio_extractor.py     # 音频提取服务
│   │   ├── speech_to_text.py      # 语音识别服务
│   │   ├── text_processor.py      # AI文本处理服务
│   │   └── video_processor.py     # 核心处理引擎
│   ├── models/            # 数据模型
│   │   └── data_models.py         # 核心数据结构
│   ├── config/            # 配置管理
│   │   └── settings.py            # 配置加载器
│   └── main.py           # Flask路由和API
├── web/                   # 前端资源
│   ├── static/
│   │   ├── css/          # 样式文件
│   │   │   └── style.css          # 主样式表
│   │   └── js/           # JavaScript文件
│   │       ├── main.js            # 主页逻辑
│   │       ├── settings.js        # 设置页逻辑
│   │       └── files.js           # 文件管理逻辑
│   └── templates/         # HTML模板
│       ├── index.html            # 主页模板
│       ├── settings.html         # 设置页模板
│       └── files.html            # 文件管理模板
├── config.yaml           # 主配置文件
├── config.docker.yaml   # Docker配置模板
├── requirements.txt      # Python依赖清单
├── run.py               # 应用启动脚本
├── temp/                # 临时文件目录
├── output/              # 输出文件目录
├── Dockerfile           # Docker镜像构建文件
├── docker-compose.yml   # Docker编排配置
├── docker-entrypoint.sh # Docker启动脚本
├── .dockerignore        # Docker构建忽略文件
├── build-docker.sh      # Linux/Mac构建脚本
├── build-docker.bat     # Windows构建脚本
└── DOCKER.md           # Docker部署指南
```

## 🔧 配置详解

### config.yaml 完整配置

```yaml
# API服务配置
apis:
  siliconflow:              # 语音识别服务
    base_url: "https://api.siliconflow.cn/v1"
    api_key: "your_siliconflow_key"
    model: "FunAudioLLM/SenseVoiceSmall"
  
  openai:                   # OpenAI服务
    api_key: "your_openai_key"
    model: "gpt-4"
    base_url: "https://api.openai.com/v1"
  
  gemini:                   # Gemini服务
    api_key: "your_gemini_key"
    model: "gemini-pro"
    base_url: "https://generativelanguage.googleapis.com/v1"

# 系统配置
system:
  temp_dir: "./temp"        # 临时文件目录
  output_dir: "./output"    # 输出文件目录
  max_file_size: 500        # 最大文件大小(MB)
  processing_timeout: 3600  # 处理超时时间(秒)
  keep_temp_files: false    # 是否保留临时文件

# 下载器配置
downloader:
  general:                  # 通用下载配置
    format: "best[height<=720]/best"
    audio_format: "bestaudio/best"
    quiet: false

# Web服务配置
web:
  host: "localhost"         # 服务器地址
  port: 5000               # 服务器端口
  debug: false             # 调试模式
```

## 📄 输出文件说明

每个处理任务会在 `/output/<task_id>/` 目录生成以下文件：

### 文本文件
- **`transcript.txt`** - 纯净逐字稿（去除时间戳）
- **`transcript_with_timestamps.txt`** - 带时间戳的完整逐字稿

### 报告文件
- **`summary.md`** - AI生成的结构化分析报告
  - 📝 内容摘要
  - 🎯 关键要点
  - 📊 情感分析
  - 🔍 深度见解

### 数据文件
- **`data.json`** - 完整的处理数据
  - 🎬 视频元信息
  - 📝 转录结果
  - 🤖 AI分析数据
  - ⏱️ 处理时间统计

### 媒体文件（临时）
- **`video.*`** - 下载的原始视频文件
- **`audio.wav`** - 提取的音频文件

## 🧪 测试系统

```bash
# 基础功能测试 - 验证核心组件
python test_simple.py

# 完整集成测试 - 端到端流程测试  
python test_complete.py

# 基础测试 - 快速功能验证
python test.py
```

### 开发命令

**传统部署**：
```bash
# 运行应用
python run.py

# 安装依赖
pip install -r requirements.txt

# FFmpeg安装 (Windows)
powershell -ExecutionPolicy Bypass -File install-ffmpeg.ps1
```

**Docker部署**：
```bash
# 构建镜像
docker build -t videowhisper:latest .

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 进入容器
docker-compose exec videowhisper bash
```

## 🎯 路线图

### 即将到来 (v2.2.0)
- [ ] **批量处理**: 支持多个视频同时处理
- [ ] **更多平台**: 支持B站、小红书等平台
- [ ] **语言支持**: 多语言界面和识别
- [ ] **AI模型**: 本地部署Whisper模型选项

### v2.3.0 计划
- [ ] **API开放**: RESTful API接口
- [ ] **用户系统**: 多用户支持和权限管理
- [ ] **云存储**: 阿里云OSS、AWS S3集成
- [ ] **实时处理**: WebSocket实时进度推送

### 长期规划
- [ ] **移动端**: PWA应用支持
- [x] **Docker**: 容器化部署 ✅
- [ ] **分布式**: 多节点处理支持
- [ ] **机器学习**: 自定义AI模型训练
- [ ] **Kubernetes**: K8s集群部署支持

## 🤝 贡献指南

我们欢迎任何形式的贡献！

### 参与方式

1. **🐛 报告问题**: [提交Issue](https://github.com/zhuguadundan/VideoWhisper/issues)
2. **💡 功能建议**: [功能请求](https://github.com/zhuguadundan/VideoWhisper/issues)
3. **📝 代码贡献**: 
   ```bash
   git fork https://github.com/zhuguadundan/VideoWhisper.git
   git checkout -b feature/amazing-feature
   git commit -m 'Add amazing feature'
   git push origin feature/amazing-feature
   # 然后提交 Pull Request
   ```

### 开发环境

```bash
# 克隆开发分支
git clone -b develop https://github.com/zhuguadundan/VideoWhisper.git

# 安装开发依赖
pip install -r requirements-dev.txt

# 运行开发服务器
python run.py --debug
```

### 代码标准

- 🐍 遵循PEP 8 Python代码规范
- 📝 添加必要的注释和文档字符串
- 🧪 为新功能编写测试
- 🎨 保持一致的代码风格

## 📊 性能指标

### 处理能力
- **视频长度**: 支持最长4小时视频
- **并发任务**: 最多5个同时处理
- **文件大小**: 最大500MB视频文件
- **识别精度**: 中文识别准确率95%+

### 系统要求
- **CPU**: 2核心以上推荐
- **内存**: 4GB以上推荐
- **存储**: 10GB可用空间
- **网络**: 稳定的互联网连接

## 🛡️ 安全说明

- 🔐 **API密钥安全**: 配置文件不包含在版本控制中
- 🚫 **路径保护**: 防止目录遍历攻击
- 🗑️ **数据清理**: 自动清理临时文件
- 🔒 **输入验证**: 严格验证用户输入

## 📄 许可证

本项目采用 **MIT 许可证** - 查看 [LICENSE](LICENSE) 文件了解详情

## ⭐ 支持项目

如果这个项目对你有帮助，请：

- ⭐ 给项目点个星
- 🍴 Fork 并分享给朋友
- 🐛 报告bug和提出建议
- 💡 贡献代码和想法

## 📧 联系方式

- 📬 **项目主页**: https://github.com/zhuguadundan/VideoWhisper
- 🐛 **问题反馈**: https://github.com/zhuguadundan/VideoWhisper/issues
- 💬 **讨论区**: https://github.com/zhuguadundan/VideoWhisper/discussions
- 📧 **邮箱联系**: zhuguadundan@example.com

## 🙏 致谢

感谢以下开源项目的支持：

- [Flask](https://flask.palletsprojects.com/) - Web框架
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 视频下载
- [FFmpeg](https://ffmpeg.org/) - 音视频处理
- [Bootstrap](https://getbootstrap.com/) - 前端框架
- [SiliconFlow](https://siliconflow.cn/) - 语音识别服务
- [OpenAI](https://openai.com/) - AI语言模型
- [Google Gemini](https://gemini.google.com/) - AI语言模型

---

<div align="center">

**VideoWhisper - 让视频内容触手可及 ✨**

[🏠 首页](https://github.com/zhuguadundan/VideoWhisper) • 
[📚 文档](https://github.com/zhuguadundan/VideoWhisper/wiki) • 
[🐛 反馈](https://github.com/zhuguadundan/VideoWhisper/issues) • 
[💬 讨论](https://github.com/zhuguadundan/VideoWhisper/discussions)

**💡 新用户提示**: 建议先在设置页面配置API密钥，然后在文件管理页面熟悉界面操作！

Made with ❤️ by VideoWhisper Team

</div>