#!/usr/bin/env python3
"""
测试脚本 - 验证系统基本功能
"""

import os
import sys

def test_imports():
    """测试模块导入"""
    print("测试模块导入...")
    try:
        from app.config.settings import Config
        from app.services.video_downloader import VideoDownloader
        from app.services.audio_extractor import AudioExtractor
        from app.services.speech_to_text import SpeechToText
        from app.services.text_processor import TextProcessor
        from app.services.video_processor import VideoProcessor
        print("[OK] 所有模块导入成功")
        return True
    except ImportError as e:
        print(f"[ERROR] 模块导入失败: {e}")
        return False

def test_config():
    """测试配置加载"""
    print("测试配置加载...")
    try:
        from app.config.settings import Config
        config = Config.load_config()
        assert 'apis' in config
        assert 'system' in config
        assert 'web' in config
        print("[OK] 配置文件加载成功")
        return True
    except Exception as e:
        print(f"[ERROR] 配置加载失败: {e}")
        return False

def test_directories():
    """测试目录结构"""
    print("测试目录结构...")
    required_dirs = ['app', 'web', 'temp', 'output']
    missing_dirs = []
    
    for dir_name in required_dirs:
        if not os.path.exists(dir_name):
            missing_dirs.append(dir_name)
    
    if missing_dirs:
        print(f"[ERROR] 缺少目录: {', '.join(missing_dirs)}")
        return False
    else:
        print("[OK] 目录结构完整")
        return True

def test_service_initialization():
    """测试服务初始化"""
    print("测试服务初始化...")
    try:
        from app.services.video_downloader import VideoDownloader
        from app.services.audio_extractor import AudioExtractor
        
        # 测试不需要API密钥的服务
        downloader = VideoDownloader()
        extractor = AudioExtractor()
        
        print("[OK] 基础服务初始化成功")
        return True
    except Exception as e:
        print(f"[ERROR] 服务初始化失败: {e}")
        return False

def test_flask_app():
    """测试Flask应用"""
    print("测试Flask应用...")
    try:
        from app import create_app
        app = create_app()
        assert app is not None
        print("[OK] Flask应用创建成功")
        return True
    except Exception as e:
        print(f"[ERROR] Flask应用创建失败: {e}")
        return False

def run_tests():
    """运行所有测试"""
    print("=" * 50)
    print("视频转文本处理系统 - 基本功能测试")
    print("=" * 50)
    
    tests = [
        test_directories,
        test_imports,
        test_config,
        test_service_initialization,
        test_flask_app
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("SUCCESS: 所有测试通过! 系统基本功能正常")
        print("\n下一步:")
        print("1. 安装FFmpeg")
        print("2. 配置API密钥 (编辑config.yaml)")
        print("3. 运行: python run.py")
    else:
        print("FAILED: 部分测试失败，请检查错误信息")
        return False
    
    return passed == total

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)