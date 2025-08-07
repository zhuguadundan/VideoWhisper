# VideoWhisper Docker 部署指南 🐳

## 快速开始

### 1. 准备工作

确保你的系统已安装：
- [Docker Desktop](https://docs.docker.com/get-docker/) (Windows/Mac)
- [Docker Engine](https://docs.docker.com/engine/install/) (Linux)
- [Docker Compose](https://docs.docker.com/compose/install/) (通常随Docker Desktop安装)

### 2. 构建镜像

**Windows用户**:
```cmd
# 使用批处理脚本
build-docker.bat

# 或手动构建
docker build -t videowhisper:latest .
```

**Linux/Mac用户**:
```bash
# 使用脚本
chmod +x build-docker.sh
./build-docker.sh

# 或手动构建
docker build -t videowhisper:latest .
```

### 3. 配置设置

```bash
# 复制配置模板
cp config.docker.yaml config.yaml

# 编辑配置文件，添加API密钥
nano config.yaml  # Linux/Mac
notepad config.yaml  # Windows
```

### 4. 启动应用

```bash
# 使用Docker Compose启动
docker-compose up -d

# 检查状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 5. 访问应用

打开浏览器访问: http://localhost:5000

## 部署配置

### 环境变量支持

```yaml
# docker-compose.yml
environment:
  - TZ=Asia/Shanghai
  - FLASK_ENV=production
  - SILICONFLOW_API_KEY=your_key_here
  - OPENAI_API_KEY=your_key_here
  - GEMINI_API_KEY=your_key_here
```

### 数据持久化

Docker Compose自动创建以下数据卷：
- `videowhisper_output`: 处理结果存储
- `videowhisper_temp`: 临时文件存储
- `videowhisper_logs`: 日志文件存储

### 自定义配置

```bash
# 挂载自定义配置
docker run -d \
  -p 5000:5000 \
  -v /host/path/config.yaml:/app/config.yaml:ro \
  -v /host/path/output:/app/output \
  videowhisper:latest
```

## 管理命令

### 基本操作

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f videowhisper

# 进入容器
docker-compose exec videowhisper bash
```

### 更新应用

```bash
# 拉取最新代码
git pull origin main

# 重新构建镜像
docker-compose build

# 重启服务
docker-compose up -d
```

### 备份数据

```bash
# 备份输出目录
docker run --rm \
  -v videowhisper_output:/source \
  -v /host/backup/path:/backup \
  busybox tar czf /backup/videowhisper-output-$(date +%Y%m%d).tar.gz -C /source .

# 备份配置
cp config.yaml /host/backup/path/
```

## 故障排除

### 常见问题

1. **端口冲突**
   ```bash
   # 修改docker-compose.yml中的端口映射
   ports:
     - "8080:5000"  # 使用8080端口
   ```

2. **配置文件问题**
   ```bash
   # 检查配置文件格式
   docker-compose config
   
   # 重新创建配置
   cp config.docker.yaml config.yaml
   ```

3. **权限问题**
   ```bash
   # Linux用户需要确保目录权限
   sudo chown -R $USER:$USER ./output ./temp ./logs
   ```

### 健康检查

```bash
# 检查容器健康状态
docker-compose ps

# 手动健康检查
curl http://localhost:5000/api/health

# 查看详细状态
docker inspect videowhisper-app | grep -A 10 Health
```

### 日志分析

```bash
# 查看应用日志
docker-compose logs videowhisper

# 查看特定时间的日志
docker-compose logs --since "2025-01-01T10:00:00" videowhisper

# 跟踪实时日志
docker-compose logs -f --tail=100 videowhisper
```

## 性能优化

### 资源限制

```yaml
# docker-compose.yml
services:
  videowhisper:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'
```

### 缓存优化

```bash
# 清理无用镜像
docker system prune -f

# 清理构建缓存
docker builder prune -f
```

## 生产部署

### 安全配置

```bash
# 使用非root用户
RUN useradd -m -u 1000 videowhisper
USER videowhisper

# 移除调试信息
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0
```

### 反向代理

```nginx
# Nginx配置示例
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 监控设置

```bash
# 添加监控容器
# Prometheus + Grafana配置
```

## 多架构支持

```bash
# 构建多架构镜像
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 -t videowhisper:latest .
```