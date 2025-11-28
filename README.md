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

### v3.7.0 (2025-11-2) - 全新UI 🚀
- ✅ 更换全新的更现代的UI界面
- ✅ 增加历史任务删除功能
- ✅ 新增环境变量MAX_UPLOAD_SIZE_MB，用于控制本地文件上传最大体积默认500MB
- ✅ 更新上游yt-dlp至最新版本修复YouTube视频转录

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

- **后端**: Python Flask + yt-dlp + FFmpeg（yt-dlp 2025.10.22 需要 Python ≥ 3.10）
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

### 上传大小限制
- 服务器端默认限制单个本地上传文件为 500MB。
- 可通过环境变量调整：`MAX_UPLOAD_SIZE_MB=2048`（单位：MB）。
- 或在 `config.yaml` 中设置：`upload.max_upload_size: 500`（被环境变量优先生效）。
- 后端同时开启 Flask `MAX_CONTENT_LENGTH` 防止大包请求，超限返回 413 及友好错误信息。
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
- 样例配置默认更严格：`security.allow_insecure_http: false`、`security.allow_private_addresses: false`；如需放宽请通过环境变量 `ALLOW_INSECURE_HTTP=true`、`ALLOW_PRIVATE_ADDRESSES=true`。
- 日志统一输出到 `logs/app.log`，对 `api_key`、`token`、`authorization` 等敏感字段做脱敏记录。
- 如需进一步限制可访问的 API 域名，可设置白名单（可选）：
   - 环境变量：`ALLOWED_API_HOSTS=api.siliconflow.cn,api.openai.com`
   - 或 `config.yaml` -> `security.allowed_api_hosts`
   - 若希望强制白名单生效（可选）：`security.enforce_api_hosts_whitelist: true` 或 `ENFORCE_API_HOSTS_WHITELIST=true`

### 兼容模式与生产建议

- 为兼容旧环境，可通过环境变量放宽策略（`ALLOW_INSECURE_HTTP=true`、`ALLOW_PRIVATE_ADDRESSES=true`）。
- 生产环境建议“严格模式”：
  - 设置 `security.allow_insecure_http: false`、`security.allow_private_addresses: false`；
  - 可启用白名单：`security.enforce_api_hosts_whitelist: true` 配合 `security.allowed_api_hosts`（或 `ALLOWED_API_HOSTS`）。

### 管理员接口鉴权（可选）

- 未配置时：为兼容旧部署，破坏性接口默认放行并打印一次安全警告（生产环境）。
- 显式配置令牌：设置环境变量 `ADMIN_TOKEN`（或在 `config.yaml` -> `security.admin_token`），前端需在请求头附带 `X-Admin-Token` 才可操作。
- 强制开启校验（可选）：`ENFORCE_ADMIN_TOKEN=true`（或 `security.enforce_admin_token: true`）。若强制开启但未配置令牌，请求将返回 403。
- 前端兼容：应用会尝试从本地 `localStorage[videowhisper_admin_token]` 或配置注入的 `security.admin_token` 自动附带头。

### HTTPS 部署建议

### 运行时环境变量（内存与代理）

- 代理透传与 HTTPS 语义（容器内 stunnel 回源）
  - `USE_PROXY_FIX=true`（默认）：启用 `ProxyFix(x_for=1, x_proto=1)` 以识别代理头。
  - `FORCE_HTTPS_SCHEME=true`（默认）：对来自本地回源的请求强制 `wsgi.url_scheme=https`，保证 URL 生成与 `Secure` Cookie 语义。
- Gunicorn 并发（默认内存优先）
  - `GUNICORN_WORKER_CLASS=sync`、`GUNICORN_WORKERS=1`、`GUNICORN_THREADS=1`、`GUNICORN_TIMEOUT=120`
  - 如需更高可用性：将 `GUNICORN_WORKERS=2`（或更高）
- glibc arena 限制（降低碎片与驻留）
  - `MALLOC_ARENA_MAX=2`（仅对 glibc 有效；镜像使用 debian/ubuntu）

说明：镜像内采用 `stunnel` 作为 TLS 终止器并回源到应用的 5000 端口；`stunnel` 不注入 `X-Forwarded-*` 头，因此应用通过上面两项开关保证 HTTPS 语义不变（Never break userspace）。
- 开发/本地：内置自签证书便于调试（端口 5443）。
- 生产：推荐由反向代理（Nginx、Caddy、Traefik）终止 TLS，再代理到应用的 HTTP/HTTPS 端口；应用内置证书仅用于本地开发。
- 说明：上述限制默认同时作用于“连接测试接口”和“实际处理接口”，行为由同一组环境变量/配置开关控制（可按需调整以兼容旧部署）。


