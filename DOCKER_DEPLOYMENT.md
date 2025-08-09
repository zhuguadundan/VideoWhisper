# Docker 部署指南

VideoWhisper 支持 Docker 容器化部署，提供了完整的视频下载和分辨率选择功能。

## 快速开始

### 1. 构建镜像
```bash
# Windows
build-docker.bat

# Linux/Mac
./build-docker.sh
```

### 2. 配置API密钥
编辑 `config.yaml` 文件，添加您的API密钥：
```yaml
apis:
  siliconflow:
    api_key: "your-siliconflow-api-key"
  openai:
    api_key: "your-openai-api-key"  # 可选
  gemini:
    api_key: "your-gemini-api-key"  # 可选
```

### 3. 启动服务
```bash
docker-compose up -d
```

### 4. 访问应用
打开浏览器访问 http://localhost:5000

## 存储结构

### 目录映射
- `./config` → `/app/config` - 配置文件
- `./output` → `/app/output` - 结果文件（持久化）
- `./temp` → `/app/temp` - 临时文件（最近3次任务）
- `./logs` → `/app/logs` - 应用日志

### 临时文件管理
- 自动保留最近3次任务的临时文件
- 超过3次任务的文件会自动清理
- 任务目录结构：`/app/temp/{task_id}/`

## 新功能特性

### 视频下载模式
1. **仅音频模式**（推荐）
   - 直接下载音频文件
   - 处理速度快，节省存储空间
   - 适合纯转录需求

2. **视频+音频模式**
   - 下载完整视频并提取音频
   - 支持多种分辨率选择
   - 适合需要视频文件的场景

### 分辨率选择
- 720p HD（默认推荐）
- 1080p Full HD
- 480p SD
- 360p
- 自动格式检测和选择

### 音频质量选项
- 128kbps（节省空间）
- 192kbps（推荐）
- 320kbps（高质量）

## 配置说明

### Docker 环境优化
```yaml
system:
  temp_dir: "/app/temp"      # 临时文件自动管理
  output_dir: "/app/output"  # 结果文件持久化
  max_file_size: 500         # 最大文件大小(MB)

downloader:
  general:
    format: "best[height<=720]/best"  # 默认720p
    quiet: true                       # 静默模式
```

### 资源要求
- **内存**: 2GB+ 推荐
- **CPU**: 1核心+ 推荐  
- **存储**: 10GB+（根据使用量调整）

## 健康检查

容器包含健康检查功能：
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5000/api/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## 常见问题

### Q: 如何更新API配置？
A: 修改 `config.yaml` 文件后重启容器：
```bash
docker-compose restart
```

### Q: 如何查看日志？
A: 
```bash
# 查看容器日志
docker-compose logs -f

# 查看应用日志文件
ls ./logs/
```

### Q: 如何清理临时文件？
A: 临时文件会自动管理，只保留最近3次任务。如需手动清理：
```bash
docker-compose exec videowhisper rm -rf /app/temp/*
```

### Q: 如何备份数据？
A: 重要数据在 `./output` 目录中，定期备份即可：
```bash
tar -czf backup-$(date +%Y%m%d).tar.gz ./output ./config
```

## 监控和维护

### 查看存储使用情况
```bash
# 查看容器磁盘使用
docker-compose exec videowhisper df -h

# 查看目录大小
docker-compose exec videowhisper du -sh /app/*
```

### 性能监控
```bash
# 查看容器资源使用
docker stats videowhisper-app
```

## 升级指南

### 1. 停止服务
```bash
docker-compose down
```

### 2. 备份数据
```bash
cp -r ./output ./output.backup
cp -r ./config ./config.backup
```

### 3. 拉取新镜像
```bash
docker pull zhugua/videowhisper:latest
```

### 4. 启动新版本
```bash
docker-compose up -d
```

## 故障排除

### 容器无法启动
1. 检查配置文件是否存在
2. 检查端口是否被占用
3. 查看容器日志：`docker-compose logs`

### 处理失败
1. 检查API密钥配置
2. 确认网络连接正常
3. 查看应用日志文件

### 权限问题
如果遇到文件权限问题，在 Linux/Mac 上：
```bash
sudo chown -R $USER:$USER ./output ./temp ./logs
```