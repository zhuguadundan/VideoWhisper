@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo 🐳 VideoWhisper Docker Build Script
echo =================================

REM 检查Docker
docker --version >nul 2>&1
if !errorlevel! neq 0 (
    echo ❌ Docker not found! Please install Docker Desktop first.
    echo Visit: https://docs.docker.com/desktop/install/windows-install/
    pause
    exit /b 1
)

REM 检查Docker Compose
docker-compose --version >nul 2>&1
if !errorlevel! neq 0 (
    echo ❌ Docker Compose not found! Please install Docker Desktop first.
    echo Visit: https://docs.docker.com/desktop/install/windows-install/
    pause
    exit /b 1
)

echo ✅ Docker and Docker Compose are available

REM 构建镜像
echo.
echo 🔨 Building Docker image...
docker build -t videowhisper:latest .

if !errorlevel! neq 0 (
    echo ❌ Failed to build Docker image
    pause
    exit /b 1
)

echo ✅ Docker image built successfully!

REM 检查配置文件
if not exist "config.yaml" (
    echo.
    echo ⚠️  config.yaml not found. Creating from template...
    copy "config.docker.yaml" "config.yaml" >nul
    echo 💡 Please edit config.yaml and add your API keys before running
)

echo.
echo =================================
echo 🎉 Build completed successfully!
echo =================================
echo Next steps:
echo 1. Edit config.yaml and add your API keys
echo 2. Run: docker-compose up -d
echo 3. Visit: http://localhost:5000
echo =================================
pause