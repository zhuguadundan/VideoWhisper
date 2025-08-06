#!/usr/bin/env python3
"""
完整系统测试 - 包含FFmpeg检测
"""

import os
import sys
import subprocess

def test_ffmpeg():
    """测试FFmpeg"""
    print("测试FFmpeg...")
    try:
        # 尝试多种方式调用ffmpeg
        ffmpeg_paths = [
            "ffmpeg",
            "C:/ffmpeg/ffmpeg.exe",
            "C:\\ffmpeg\\ffmpeg.exe"
        ]
        
        ffmpeg_working = False
        for ffmpeg_path in ffmpeg_paths:
            try:
                result = subprocess.run([ffmpeg_path, "-version"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    print(f"[OK] FFmpeg工作正常 - 路径: {ffmpeg_path}")
                    version_line = result.stdout.split('\n')[0]
                    print(f"     版本: {version_line}")
                    ffmpeg_working = True
                    break
            except:
                continue
        
        if not ffmpeg_working:
            print("[ERROR] FFmpeg未找到或无法运行")
            return False
        
        return True
    except Exception as e:
        print(f"[ERROR] FFmpeg测试失败: {e}")
        return False

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

def test_api_keys():
    """测试API密钥配置"""
    print("测试API密钥配置...")
    try:
        from app.config.settings import Config
        
        siliconflow_config = Config.get_api_config('siliconflow')
        openai_config = Config.get_api_config('openai')
        gemini_config = Config.get_api_config('gemini')
        
        # 检查硅基流动
        if siliconflow_config.get('api_key') and siliconflow_config['api_key'] != 'your_siliconflow_api_key':
            print("[OK] 硅基流动API密钥已配置")
        else:
            print("[WARN] 硅基流动API密钥未配置")
        
        # 检查OpenAI
        if openai_config.get('api_key') and openai_config['api_key'] != 'your_openai_api_key':
            print("[OK] OpenAI API密钥已配置")
        else:
            print("[WARN] OpenAI API密钥未配置")
        
        # 检查Gemini
        if gemini_config.get('api_key') and gemini_config['api_key'] != 'your_gemini_api_key':
            print("[OK] Gemini API密钥已配置")
        else:
            print("[WARN] Gemini API密钥未配置（可选）")
        
        return True
    except Exception as e:
        print(f"[ERROR] API密钥配置检查失败: {e}")
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

def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("视频转文本处理系统 - 完整系统测试")
    print("=" * 60)
    
    tests = [
        ("目录结构", test_directories),
        ("模块导入", test_imports), 
        ("配置加载", test_config),
        ("API密钥", test_api_keys),
        ("FFmpeg", test_ffmpeg),
        ("服务初始化", test_service_initialization)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n[{test_name}]")
        if test_func():
            passed += 1
        print()
    
    print("=" * 60)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 SUCCESS: 所有测试通过! 系统准备就绪")
        print("\n✅ 可以开始使用:")
        print("1. 运行: python run.py")
        print("2. 访问: http://localhost:5000")
        print("3. 输入视频URL并开始处理")
    else:
        print("⚠️  ATTENTION: 部分测试失败")
        if passed >= 4:  # 关键组件正常
            print("核心功能可以使用，但建议检查失败项")
        else:
            print("请解决失败的测试项后再使用")
    
    return passed == total

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)