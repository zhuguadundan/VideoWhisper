# 使用Python官方镜像作为基础镜像
FROM python:3.9-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ffmpeg -version \
    && ffprobe -version

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p /app/temp /app/output /app/logs

# 复制启动脚本和配置模板
COPY docker-entrypoint.sh /app/
COPY config.docker.yaml /app/config.yaml.example

# 设置权限
RUN chmod +x /app/docker-entrypoint.sh

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# 设置启动命令
CMD ["/app/docker-entrypoint.sh"]