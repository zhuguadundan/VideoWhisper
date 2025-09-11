@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo 🐳 VideoWhisper Docker Build Script v1.2.0
echo ============================================

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

REM 检查Docker Compose插件 (支持新版Docker Desktop)
docker compose version >nul 2>&1
if !errorlevel! equ 0 (
    set COMPOSE_CMD=docker compose
) else (
    docker-compose --version >nul 2>&1
    if !errorlevel! equ 0 (
        set COMPOSE_CMD=docker-compose
    ) else (
        set COMPOSE_CMD=docker-compose
    )
)

echo 📋 Using command: %COMPOSE_CMD%

REM 构建镜像
echo.
echo 🔨 Building Docker image zhugua/videowhisper v1.2...
docker build -t zhugua/videowhisper:1.2 -t zhugua/videowhisper:latest .

if !errorlevel! neq 0 (
    echo ❌ Failed to build Docker image
    pause
    exit /b 1
)

echo ✅ Docker image zhugua/videowhisper v1.2 built successfully!
echo 🏷️  Tags: zhugua/videowhisper:1.2, zhugua/videowhisper:latest

REM 检查配置文件和创建目录结构
if not exist "config.yaml" (
    echo.
    echo ⚠️  config.yaml not found. Creating from template...
    copy "config.docker.yaml" "config.yaml" >nul
    echo 💡 Please edit config.yaml and add your API keys before running
)

REM 创建必要的目录结构
echo.
echo 📁 Creating directory structure for new storage management...
if not exist "output" mkdir output
if not exist "temp" mkdir temp
if not exist "logs" mkdir logs
if not exist "config" (
    mkdir config
    if exist "config.yaml" copy "config.yaml" "config\config.yaml" >nul
    echo 📋 Config file copied to config\ directory
)

echo ✅ Directory structure ready (temp files auto-managed, keeps latest 3 tasks)

echo.
echo ============================================
echo 🎉 Build completed successfully!
echo ============================================
echo Next steps:
echo 1. Edit config.yaml and add your API keys
echo 2. Run: %COMPOSE_CMD% up -d
echo 3. HTTP interface: http://localhost:5000
echo 4. HTTPS interface: https://localhost:5443 (self-signed)
echo 5. View logs: %COMPOSE_CMD% logs -f
echo ============================================
echo.
echo 💡 Tips:
echo    - HTTPS uses self-signed certificate (browser warning expected)
echo    - To disable HTTPS: set HTTPS_ENABLED=false in docker-compose.yml
echo    - API check: curl http://localhost:5000/api/providers
echo    - HTTPS check: curl -k https://localhost:5443/api/providers
echo.
echo 🚀 Quick test commands:
echo    # Test HTTP
echo    curl -f http://localhost:5000/api/providers
echo    # Test HTTPS
echo    curl -k -f https://localhost:5443/api/providers
echo    # View logs
echo    %COMPOSE_CMD% logs -f videowhisper
echo ============================================
pause
