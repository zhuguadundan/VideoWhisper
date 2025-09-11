#!/bin/bash

# VideoWhisper Docker构建和测试脚本 (v1.1.0)
# 兼容Windows和Linux/macOS

set -e

# 检测操作系统
OS="$(uname -s)"
case "${OS}" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    CYGWIN*)    MACHINE=Cygwin;;
    MINGW*)     MACHINE=MinGW;;
    MSYS_NT*)   MACHINE=Git;;
    *)          MACHINE="UNKNOWN:${OS}"
esac

if [ "${MACHINE}" = "MinGW" ] || [ "${MACHINE}" = "Cygwin" ] || [ "${MACHINE}" = "Git" ]; then
    echo -e "${YELLOW}🪟 Detected Windows environment${NC}"
fi

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}🐳 VideoWhisper Docker Build Script v1.1.0${NC}"
echo -e "${CYAN}===========================================${NC}"

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found! Please install Docker first.${NC}"
    echo -e "${YELLOW}Visit: https://docs.docker.com/get-docker/${NC}"
    exit 1
fi

# 检查Docker Compose (同时检查docker compose插件)
DOCKER_COMPOSE_CMD=""
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo -e "${RED}❌ Docker Compose not found! Please install Docker Compose first.${NC}"
    echo -e "${YELLOW}Visit: https://docs.docker.com/compose/install/${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker and Docker Compose are available${NC}"
echo -e "${BLUE}📋 Using command: ${DOCKER_COMPOSE_CMD}${NC}"

# 构建镜像
echo -e "${YELLOW}🔨 Building Docker image zhugua/videowhisper v1.2...${NC}"
docker build -t zhugua/videowhisper:1.2 -t zhugua/videowhisper:latest .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Docker image zhugua/videowhisper v1.2 built successfully!${NC}"
    echo -e "${PURPLE}🏷️  Tags: zhugua/videowhisper:1.2, zhugua/videowhisper:latest${NC}"
else
    echo -e "${RED}❌ Failed to build Docker image${NC}"
    exit 1
fi

# 检查配置文件和创建目录结构
if [ ! -f "config.yaml" ]; then
    echo -e "${YELLOW}⚠️  config.yaml not found. Creating from template...${NC}"
    cp config.docker.yaml config.yaml
    echo -e "${YELLOW}💡 Please edit config.yaml and add your API keys before running${NC}"
fi

# 创建必要的目录结构
echo -e "${YELLOW}📁 Creating directory structure for new storage management...${NC}"
mkdir -p output temp logs config

# 设置目录权限
chmod 755 output temp logs config 2>/dev/null || true

# 如果config.yaml存在，复制到config目录
if [ -f "config.yaml" ]; then
    cp config.yaml config/config.yaml
    echo -e "${BLUE}📋 Config file copied to config/ directory${NC}"
fi

echo -e "${GREEN}✅ Directory structure ready (temp files auto-managed, keeps latest 3 tasks)${NC}"

echo -e "${CYAN}===========================================${NC}"
echo -e "${GREEN}🎉 Build completed successfully!${NC}"
echo -e "${CYAN}===========================================${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo -e "${YELLOW}1. Edit config.yaml and add your API keys${NC}"
echo -e "${YELLOW}2. Run: ${DOCKER_COMPOSE_CMD} up -d${NC}"
echo -e "${YELLOW}3. HTTP interface: http://localhost:5000${NC}"
echo -e "${YELLOW}4. HTTPS interface: https://localhost:5443 (self-signed)${NC}"
echo -e "${PURPLE}5. View logs: ${DOCKER_COMPOSE_CMD} logs -f${NC}"
echo -e "${CYAN}===========================================${NC}"

# 显示一些有用的提示
echo -e "${BLUE}💡 Tips:${NC}"
echo -e "${BLUE}   - HTTPS uses self-signed certificate (browser warning expected)${NC}"
echo -e "${BLUE}   - To disable HTTPS: set HTTPS_ENABLED=false in docker-compose.yml${NC}"
echo -e "${BLUE}   - API check: curl http://localhost:5000/api/providers${NC}"
echo -e "${BLUE}   - HTTPS check: curl -k https://localhost:5443/api/providers${NC}"
echo ""
echo -e "${CYAN}🚀 Quick test commands:${NC}"
echo -e "${YELLOW}   # Test HTTP${NC}"
echo -e "${YELLOW}   curl -f http://localhost:5000/api/providers || echo 'HTTP failed'${NC}"
echo ""
echo -e "${YELLOW}   # Test HTTPS${NC}"
echo -e "${YELLOW}   curl -k -f https://localhost:5443/api/providers || echo 'HTTPS failed'${NC}"
echo ""
echo -e "${YELLOW}   # View logs${NC}"
echo -e "${YELLOW}   ${DOCKER_COMPOSE_CMD} logs -f videowhisper${NC}"
