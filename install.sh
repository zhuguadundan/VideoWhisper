#!/bin/bash

echo "视频转文本处理系统 - 安装脚本"
echo "========================================"

# 检查Python版本
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python 3.8+"
    exit 1
fi

echo "检查Python版本..."
python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"
if [ $? -ne 0 ]; then
    echo "错误: Python版本过低，需要Python 3.8+"
    exit 1
fi
echo "✓ Python版本符合要求"

# 询问是否创建虚拟环境
read -p "是否创建虚拟环境? (y/n): " create_venv
if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo "创建虚拟环境..."
    python3 -m venv video-text-env
    source video-text-env/bin/activate
fi

# 安装依赖
echo "安装Python依赖..."
pip install -r requirements.txt

# 检查FFmpeg
echo "检查FFmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  警告: 未找到FFmpeg"
    echo "请安装FFmpeg:"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  macOS: brew install ffmpeg"
    echo "  CentOS/RHEL: sudo yum install ffmpeg"
else
    echo "✓ FFmpeg已安装"
fi

# 复制配置文件
echo "准备配置文件..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✓ 已创建.env文件，请填入你的API密钥"
fi

# 设置权限
chmod +x test.py
chmod +x run.py

# 运行测试
echo "运行系统测试..."
python3 test.py

echo
echo "安装完成!"
echo
echo "下一步:"
echo "1. 编辑config.yaml文件，填入API密钥"
echo "2. 运行: python3 run.py"
echo "3. 打开浏览器访问: http://localhost:5000"
echo