# VideoWhisper - 视频智语 🎥✨

> 当前版本：v3.3.0 | 最后更新：2025-08-23

本项目完全依赖硅基流动服务，如未注册请点击下方邀请链接注册可获14元赠金
https://cloud.siliconflow.cn/i/uy4d8V8Y

智能视频转文本处理系统，支持语音转录和AI内容分析。仅需一个硅基流动API即可完成全流程


**免责声明**
本项目100%由claude-sonnet-4开发，请谨慎公网使用

## ✨ 功能特性

- 🎬 **视频处理**: 支持YouTube\bilibili等主流平台，自动下载转录
- 🤖 **AI分析**: 集成硅基流动进行智能摘要和内容分析  
- 📁 **文件管理**: 完整的任务历史和文件批量管理
- ⚙️ **在线配置**: Web界面直接配置API密钥
- 🐳 **容器部署**: Docker一键部署，简单易用

## 📈 版本更新

### v3.3.0 (2025-08-23) - 自签https支持 🚀
- ✅ obsidian导入由于浏览器安全限制必须本地启动或者启动https，添加开箱即用的自签https证书默认端口5443（需更新dockercompose），同时保留http访问，最新镜像已上传dockerhub
- ✅ 同时支持外部反向代理，可以直接用npm、lucky等可视化反向代理工具直接反向代理http5000端口

### v3.2.0 (2025-08-19) - debug 🚀
- ✅ 修复TranscriptionSegment初始化参数错误导致小于5分钟的短视频无法生成逐字稿
- ✅ 修复处理视频阶段上传者会复用上个视频信息的问题


### v3.1.0 (2025-08-18) - obsidian 🚀
- ✅ 修复超过4000字后文本截断的问题
- ✅ 修复自定义AI文本分析base url不生效的问题
- ✅ 新增obsidian一键导入功能
- ✅ 修改逐字稿下载格式弃用TXT改用markdown

### v3.0.5 (2025-08-09) - 容器优化 🚀
- ✅ 进度条每个阶段都有具体的描述和进度详情
- ✅ 转录完成后立即显示逐字稿，无需等待总结分析完成
- ✅ 为逐字稿增加一键复制功能

### v3.0.0 (2025-08-07) - 容器化重构 🚀
- ✅ Docker容器化部署优化
- ✅ 系统架构重构和性能提升
- ✅ 简化配置管理和部署流程
- ✅ 增强错误处理和日志系统

### v2.1.1 (2025-08-06) - 任务管理优化
- ✅ 任务管理系统优化
- ✅ 文件管理和批量操作增强
- ✅ 系统稳定性和性能提升

## 🛠️ 技术栈

- **后端**: Python Flask + yt-dlp + FFmpeg
- **AI服务**: SiliconFlow语音识别 + OpenAI/Gemini文本处理
- **前端**: Bootstrap 5 + JavaScript
- **部署**: Docker容器化

## 🚀 快速开始

详细图文教程可见[公众号文章](https://mp.weixin.qq.com/s/DOTWF3UGV9Dvi3xQxAfJcg)

### Docker部署（推荐）

下载docker-compose.yml文件
修改端口和存储目录
cd到compose文件目录执行
`docker-compose up -d`

或者执行docker run命令（仅测试用，无持久化存储重启后数据丢失）
`docker run -d --name videowhisper -p 5000:5000 zhugua/videowhisper:latest`

### 传统部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 安装FFmpeg
 Windows: powershell -ExecutionPolicy Bypass -File install-ffmpeg-en.ps1
# Linux: sudo apt install ffmpeg
# macOS: brew install ffmpeg

# 3. 运行应用
python run.py
```

## 📖 使用指南

1. **配置API密钥**: 访问设置页面配置SiliconFlow密钥
2. **处理视频**: 输入视频URL，选择AI模型，开始处理
3. **查看结果**: 自动生成文本转录、智能摘要和分析报告
4. **文件管理**: 在文件页面管理所有处理结果

## 📁 输出文件

每个处理任务生成的文件：

- **transcript.txt** - 纯净文字转录
- **summary.md** - AI智能摘要报告  
- **data.json** - 完整处理数据

## 🧪 测试

```bash
python test_simple.py      # 基础组件测试
python test_complete.py    # 完整集成测试
```

## 📄 许可证

本项目采用 **MIT 许可证**

---

**VideoWhisper - 让视频内容触手可及 ✨**

[🏠 首页](https://github.com/zhuguadundan/VideoWhisper) • [🐛 反馈](https://github.com/zhuguadundan/VideoWhisper/issues)

Made with ❤️ by VideoWhisper Team