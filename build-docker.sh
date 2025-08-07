#!/bin/bash

# VideoWhisper Docker构建和测试脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🐳 VideoWhisper Docker Build Script${NC}"
echo -e "${BLUE}=================================${NC}"

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found! Please install Docker first.${NC}"
    echo -e "${YELLOW}Visit: https://docs.docker.com/get-docker/${NC}"
    exit 1
fi

# 检查Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found! Please install Docker Compose first.${NC}"
    echo -e "${YELLOW}Visit: https://docs.docker.com/compose/install/${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker and Docker Compose are available${NC}"

# 构建镜像
echo -e "${YELLOW}🔨 Building Docker image...${NC}"
docker build -t videowhisper:latest .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Docker image built successfully!${NC}"
else
    echo -e "${RED}❌ Failed to build Docker image${NC}"
    exit 1
fi

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    echo -e "${YELLOW}⚠️  config.yaml not found. Creating from template...${NC}"
    cp config.docker.yaml config.yaml
    echo -e "${YELLOW}💡 Please edit config.yaml and add your API keys before running${NC}"
fi

echo -e "${BLUE}=================================${NC}"
echo -e "${GREEN}🎉 Build completed successfully!${NC}"
echo -e "${BLUE}=================================${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo -e "${YELLOW}1. Edit config.yaml and add your API keys${NC}"
echo -e "${YELLOW}2. Run: docker-compose up -d${NC}"
echo -e "${YELLOW}3. Visit: http://localhost:5000${NC}"
echo -e "${BLUE}=================================${NC}"