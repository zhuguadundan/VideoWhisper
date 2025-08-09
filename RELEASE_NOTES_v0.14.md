# VideoWhisper v0.14.0 发布说明

## 🎯 核心简化

### 📥 专注音频处理
- **仅音频模式**: 专注于音频下载和处理，提供最佳性能
- **简化界面**: 移除复杂的视频下载选项，操作更直观
- **优化流程**: 精简处理管道，减少不必要的功能复杂度

### 🔧 系统优化

#### API 简化
- 简化 `POST /api/process` 端点，仅支持音频处理
- 移除 `POST /api/formats` 格式检测端点
- 保持 `POST /api/video-info` 基本信息获取
- 清理健康检查端点，显示简化功能列表

#### 数据模型简化
- **ProcessingTask**: 移除视频相关字段，仅保留 `audio_file_path`
- **VideoDownloader**: 简化为仅支持 `download_audio_only()` 方法
- **前端界面**: 移除视频质量选择和格式检测功能

### 📁 保持核心功能
- **智能临时文件管理**: 保留最近3次任务文件的智能清理系统
- **多AI提供商支持**: 继续支持 SiliconFlow、OpenAI、Gemini
- **完整处理流程**: 语音识别 → 文本优化 → 总结分析
- **文件管理**: 完整的文件下载和管理功能

## 🐳 Docker 部署

### 构建镜像
```bash
# Windows
build-docker.bat

# Linux/Mac  
./build-docker.sh
```

### 启动服务
```bash
docker-compose up -d
```

### 版本验证
```bash
curl http://localhost:5000/api/health
```

## 📋 版本信息

- **版本号**: v0.14.0
- **构建日期**: 2025-08-08  
- **镜像标签**: `videowhisper:0.14`, `videowhisper:latest`
- **基础镜像**: python:3.9-slim
- **FFmpeg版本**: 5.1.6

## 🎯 功能特性标识

健康检查接口现在返回简化的功能列表：
```json
{
  "version": "v0.14.0",
  "status": "healthy", 
  "features": [
    "audio_only_download",
    "automatic_temp_cleanup",
    "docker_optimized"
  ]
}
```

## 🔄 从 v0.13 升级

### 主要变化
- **移除功能**: 视频下载模式、分辨率选择、格式检测
- **保持功能**: 音频处理、AI文本处理、文件管理
- **界面简化**: 更直观的操作流程

### 升级步骤
1. 停止现有容器: `docker-compose down`
2. 重新构建镜像: `build-docker.bat` 或 `./build-docker.sh`
3. 启动新版本: `docker-compose up -d`
4. 验证功能: 访问 `http://localhost:5000`

## 🌟 设计理念

v0.14 专注于核心用户需求：
- **简单高效**: 专注音频转文本的核心功能
- **稳定可靠**: 移除复杂功能，提高系统稳定性
- **易于使用**: 简化界面，降低学习成本
- **性能优先**: 优化处理流程，提升转换效率

## 🐛 技术改进

- 移除复杂的视频格式检测逻辑
- 简化前端JavaScript，减少代码复杂度
- 优化Docker镜像大小和启动时间
- 提升系统整体稳定性和可维护性

## 🚀 适用场景

v0.14 特别适合：
- 播客、会议录音转文字
- 教学视频音频提取和转录
- 访谈节目内容分析
- 音频内容的快速文字化需求

---

**感谢使用VideoWhisper！** 如有问题或建议，请访问项目仓库提交Issue。