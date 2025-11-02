# 使用Python官方镜像作为基础镜像
FROM python:3.9-slim

# 版本参数（单一来源）
ARG APP_VERSION=1.2.0

# 设置版本标签
LABEL version="${APP_VERSION}"
LABEL description="VideoWhisper - AI视频转文本处理平台，版本 ${APP_VERSION}"
LABEL maintainer="VideoWhisper Team"

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    APP_VERSION=${APP_VERSION}

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

# 创建必要的目录和设置权限
RUN mkdir -p /app/temp /app/output /app/logs /app/config && \
    chmod 755 /app/temp /app/output /app/logs /app/config && \
    # 创建临时目录的任务历史文件占位符
    touch /app/temp/.task_history.json && \
    chmod 644 /app/temp/.task_history.json

# 复制启动脚本和配置模板
COPY docker-entrypoint.sh /app/
COPY config.docker.yaml /app/config.yaml.example

# 转换换行符并设置权限
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh

# 暴露端口
EXPOSE 5000 5443

# 健康检查已移除，避免周期性请求造成日志噪声

# 设置启动命令
CMD ["/app/docker-entrypoint.sh"]
