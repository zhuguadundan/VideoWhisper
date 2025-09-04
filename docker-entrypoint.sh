#!/bin/bash
set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}VideoWhisper Docker Container Starting...${NC}"
echo -e "${BLUE}======================================${NC}"

# 检查配置文件
echo -e "${YELLOW}Checking configuration...${NC}"
if [ ! -f "/app/config.yaml" ]; then
    echo -e "${RED}config.yaml not found!${NC}"
    echo -e "${YELLOW}Please mount your config.yaml file or create one based on template.${NC}"
    echo -e "${YELLOW}   Example: docker run -v /host/path/config.yaml:/app/config.yaml${NC}"
    exit 1
else
    echo -e "${GREEN}Configuration file found${NC}"
fi

# 检查必要目录和文件权限
echo -e "${YELLOW}Checking directories and permissions...${NC}"
mkdir -p /app/temp /app/output /app/logs /app/config

# 确保临时文件管理所需的文件存在
if [ ! -f "/app/temp/.task_history.json" ]; then
    echo '[]' > /app/temp/.task_history.json
    chmod 644 /app/temp/.task_history.json
fi

# 检查目录权限
chmod 755 /app/temp /app/output /app/logs /app/config 2>/dev/null || true

echo -e "${GREEN}Directories and permissions ready${NC}"

# 显示存储结构信息
echo -e "${BLUE}Storage Structure:${NC}"
echo -e "${BLUE}   - Output: /app/output (persistent results)${NC}"
echo -e "${BLUE}   - Temp: /app/temp (latest 3 tasks only)${NC}"
echo -e "${BLUE}   - Logs: /app/logs${NC}"
echo -e "${BLUE}   - Config: /app/config${NC}"

# 检查FFmpeg
echo -e "${YELLOW}Checking FFmpeg...${NC}"
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version | head -n 1 | cut -d ' ' -f 3)
    echo -e "${GREEN}FFmpeg $FFMPEG_VERSION is available${NC}"
else
    echo -e "${RED}FFmpeg not found!${NC}"
    exit 1
fi

# 检查Python环境
echo -e "${YELLOW}Checking Python environment...${NC}"
python --version
echo -e "${GREEN}Python environment ready${NC}"

# 显示系统信息
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}System Information:${NC}"
echo -e "${BLUE}   - Python: $(python --version)${NC}"
echo -e "${BLUE}   - FFmpeg: $FFMPEG_VERSION${NC}"
echo -e "${BLUE}   - Working Directory: $(pwd)${NC}"
echo -e "${BLUE}   - Container User: $(whoami)${NC}"
echo -e "${BLUE}======================================${NC}"

# 检查HTTPS配置
HTTPS_ENABLED=${HTTPS_ENABLED:-true}
HTTPS_PORT=${HTTPS_PORT:-5443}
echo -e "${GREEN}Dual protocol mode enabled${NC}"
echo -e "${GREEN}HTTP interface:  http://localhost:5000${NC}"
echo -e "${GREEN}HTTPS interface: https://localhost:${HTTPS_PORT}${NC}"
echo -e "${YELLOW}Note: HTTPS uses self-signed certificate, browser may show security warning${NC}"

# 检查证书文件状态
if [ "$HTTPS_ENABLED" = "true" ]; then
    echo -e "${YELLOW}Checking SSL certificates...${NC}"
    if [ -f "/app/config/cert.pem" ] && [ -f "/app/config/key.pem" ]; then
        echo -e "${GREEN}SSL certificates found${NC}"
    else
        echo -e "${YELLOW}SSL certificates not found, will be auto-generated${NC}"
    fi
fi

# 启动应用
echo -e "${GREEN}Starting VideoWhisper Application...${NC}"
echo -e "${BLUE}======================================${NC}"

# 启动Flask应用
exec python run.py