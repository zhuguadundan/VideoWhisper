# VideoWhisper - 视频智语 🎥✨

> 当前版本：v3.6.0 | 最后更新：2025-09-10

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

### v3.6.0 (2025-09-10) - 支持中英对照翻译 🚀
- ✅ 新增按钮一键翻译成中英文句对句翻译版
- ✅ review代码修复大量微小错误及安全性提升，防止文件路径遍历，日志脱敏
- ✅ 新增白名单功能，启用请在compose中添加环境变量ALLOWED_API_HOSTS=你的域名

### v3.5.0 (2025-09-03) - 支持本地音视频上传 🚀
- ✅ 支持本地音视频上传转录逐字稿
- ✅ 新增一键停止所有任务按钮
- ✅ 新镜像已推送dockerhub

### v3.4.0 (2025-08-24) - debug 🚀
- ✅ YouTube加强了反机器人措施，要求使用PO Token（Proof of Origin Token）进行身份验证，最新镜像更新yt-dlp到最新版并更新cookie处理方式已修复此问题

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
 
# 4. 运行最小化冒烟测试（可选）
pytest -q
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

## ⚙️ 可调处理参数（config.yaml）
- `processing.long_audio_threshold_seconds`：超过该秒数视为长音频（默认 300）
- `processing.segment_duration_seconds`：长音频分段长度（默认 300）
- `processing.max_consecutive_failures`：分段连续失败上限（默认 3）
- `processing.short_audio_max_retries`：短音频重试次数（默认 3）
- `processing.retry_sleep_short_seconds` / `retry_sleep_long_seconds`：成功/失败后的轻度退避（默认 1.0/2.0）

## 🧪 测试

```bash
python test_simple.py      # 基础组件测试
python test_complete.py    # 完整集成测试
```

## 📄 许可证

本项目采用 **MIT 许可证**

## 致谢

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) 
- [硅基流动](https://cloud.siliconflow.cn/) 

---

**VideoWhisper - 让视频内容触手可及 ✨**

[🏠 首页](https://github.com/zhuguadundan/VideoWhisper) • [🐛 反馈](https://github.com/zhuguadundan/VideoWhisper/issues)

Made with ❤️ by VideoWhisper Team

## 安全说明（重要）

- 文件接口已加路径校验，下载/删除仅限 `temp/` 与 `output/` 范围，防止路径遍历。
- API 连接测试对自定义 Base URL 做基础校验以降低 SSRF 风险；已提供开关以兼容更多部署：
- 允许 `http`（默认开启，方便升级用户无缝使用）：`security.allow_insecure_http: true` 或环境变量 `ALLOW_INSECURE_HTTP=true`。
- 允许私网/本地地址（默认开启）：`security.allow_private_addresses: true` 或 `ALLOW_PRIVATE_ADDRESSES=true`。
- 日志统一输出到 `logs/app.log`，对 `api_key`、`token`、`authorization` 等敏感字段做脱敏记录。
- 如需进一步限制可访问的 API 域名，可设置白名单（可选）：
   - 环境变量：`ALLOWED_API_HOSTS=api.siliconflow.cn,api.openai.com`
   - 或 `config.yaml` -> `security.allowed_api_hosts`
   - 若希望强制白名单生效（可选）：`security.enforce_api_hosts_whitelist: true` 或 `ENFORCE_API_HOSTS_WHITELIST=true`

### 兼容模式与生产建议

- 为兼容已有用户与自建反代，连接测试接口默认允许 `http` 与私网/本地地址（即 `security.allow_insecure_http: true` 与 `security.allow_private_addresses: true`）。
- 生产环境建议改为“严格模式”以降低 SSRF 风险：
  - 设置 `security.allow_insecure_http: false`、`security.allow_private_addresses: false`；
  - 并启用白名单：`security.enforce_api_hosts_whitelist: true`，配合 `security.allowed_api_hosts`（或环境变量 `ALLOWED_API_HOSTS`）。
- 说明：上述限制默认同时作用于“连接测试接口”和“实际处理接口”，行为由同一组环境变量/配置开关控制（可按需调整以兼容旧部署）。

## 维护者说明（近期技术改动）

- 证书 SAN 修复：自签证书的 `SubjectAlternativeName` 现在正确包含 IP（使用 `ipaddress`），构造失败将记录告警并回退到仅域名 SAN（行为不变）。
- 文件名清洗统一：所有文件名规范化统一由 `app/utils/helpers.py:sanitize_filename` 提供，保证 Windows 规则一致（替换非法字符、去除首尾空格与点、长度限制、空名回退）。
- 连接测试收敛：不同提供商（SiliconFlow/OpenAI 兼容/Gemini）的连接测试已收敛到 `app/utils/provider_tester.py`，路由层仅做参数校验与安全校验。
- 启动安全提示：保持默认兼容（允许 http/私网）不变，但启动时在日志里输出一次“生产建议关闭”的提示，便于逐步收紧。
- 日志统一：服务层（downloader/audio_extractor/speech_to_text/file_uploader/file_manager）已统一使用 `logging.getLogger(__name__)`，去除 `print` 重定向；后续可按需将 `video_processor` 也全部替换为直接 `logger` 调用（当前其内部 `print` 已路由到日志，行为一致）。
