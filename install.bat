@echo off
echo 视频转文本处理系统 - 安装脚本
echo ========================================

REM 检查Python版本
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

echo 检查Python版本...
python -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"
if %errorlevel% neq 0 (
    echo 错误: Python版本过低，需要Python 3.8+
    pause
    exit /b 1
)

echo ✓ Python版本符合要求

REM 创建虚拟环境（可选）
set /p create_venv="是否创建虚拟环境? (y/n): "
if /i "%create_venv%"=="y" (
    echo 创建虚拟环境...
    python -m venv video-text-env
    call video-text-env\Scripts\activate.bat
)

REM 安装依赖
echo 安装Python依赖...
pip install -r requirements.txt

REM 检查FFmpeg
echo 检查FFmpeg...
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  警告: 未找到FFmpeg
    echo 请从 https://ffmpeg.org/download.html 下载并安装FFmpeg
    echo 或使用包管理器安装: choco install ffmpeg
) else (
    echo ✓ FFmpeg已安装
)

REM 准备配置文件
echo 准备配置文件...
if not exist config.yaml (
    echo 请手动创建config.yaml文件，填入你的API密钥
    echo 可参考项目文档中的配置示例
)

REM 运行测试
echo 运行系统测试...
python test.py

echo.
echo 安装完成!
echo.
echo 下一步:
echo 1. 编辑config.yaml文件，填入API密钥
echo 2. 运行: python run.py
echo 3. 打开浏览器访问: http://localhost:5000
echo.
pause