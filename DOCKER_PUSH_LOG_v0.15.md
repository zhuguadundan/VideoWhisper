# VideoWhisper Docker Hub 推送记录

## 📦 推送信息

**推送时间**: 2025-08-09  
**用户名**: zhugua  
**仓库**: zhugua/videowhisper

## 🏷️ 推送的镜像标签

### v0.15 版本
- **标签**: `zhugua/videowhisper:0.15`
- **镜像ID**: 148358ce1a8f
- **大小**: 1.18GB
- **摘要**: sha256:148358ce1a8f6810e96dc849e66c217a71f81877eb0af33526bc50e51cbab031
- **状态**: ✅ 推送成功

### Latest 版本
- **标签**: `zhugua/videowhisper:latest`
- **镜像ID**: 148358ce1a8f (与v0.15相同)
- **大小**: 1.18GB
- **摘要**: sha256:148358ce1a8f6810e96dc849e66c217a71f81877eb0af33526bc50e51cbab031
- **状态**: ✅ 推送成功

## 🎯 版本特性

VideoWhisper v0.15 包含以下主要特性：
- ✨ 智能进度显示与阶段图标
- 🤖 AI响应时间实时监控
- 📂 智能文件命名系统
- 🎨 逐字稿即时预览功能
- 🌟 优化的用户交互体验

## 🚀 使用方式

### 快速启动
```bash
# 拉取最新版本
docker pull zhugua/videowhisper:latest

# 或指定版本
docker pull zhugua/videowhisper:0.15

# 运行容器
docker run -d -p 5000:5000 \
  --name videowhisper \
  -v ./config:/app/config \
  -v ./output:/app/output \
  -v ./temp:/app/temp \
  -v ./logs:/app/logs \
  zhugua/videowhisper:0.15
```

### Docker Compose 部署
```yaml
services:
  videowhisper:
    image: zhugua/videowhisper:0.15
    container_name: videowhisper-app
    ports:
      - "5000:5000"
    volumes:
      - ./config:/app/config
      - ./output:/app/output
      - ./temp:/app/temp
      - ./logs:/app/logs
    environment:
      - TZ=Asia/Shanghai
      - FLASK_ENV=production
      - APP_VERSION=0.15.0
    restart: unless-stopped
```

## 📊 镜像层信息

推送包含以下镜像层：
- 基础Python 3.9-slim环境
- FFmpeg音视频处理工具
- Python依赖包
- 应用程序代码
- 配置文件和启动脚本

## 🔗 访问链接

- **Docker Hub页面**: https://hub.docker.com/r/zhugua/videowhisper
- **拉取命令**: `docker pull zhugua/videowhisper:0.15`
- **项目文档**: 查看仓库README获取详细使用说明

## ✅ 验证状态

- [x] 镜像构建成功
- [x] 标签创建完成
- [x] Docker Hub登录正常
- [x] v0.15版本推送成功
- [x] latest标签推送成功
- [x] 镜像在Docker Hub可搜索到

---

**推送完成时间**: 2025-08-09
**总耗时**: 约5分钟
**网络传输**: 成功利用层缓存，提高推送效率