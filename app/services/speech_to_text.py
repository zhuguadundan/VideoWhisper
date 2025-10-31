import requests
import json
import time
import os
from typing import List, Dict, Any
from app.config.settings import Config
import logging

logger = logging.getLogger(__name__)

class SpeechToText:
    def __init__(self, api_config=None):
        if api_config:
            self.config = api_config
        else:
            self.config = Config.get_api_config('siliconflow')
        
        self.api_key = self.config.get('api_key', '')
        # 默认使用硅基流动正式基址，去掉结尾斜杠以便拼接端点
        self.base_url = (self.config.get('base_url') or 'https://api.siliconflow.cn/v1').rstrip('/')
        self.model = self.config.get('model', 'FunAudioLLM/SenseVoiceSmall')
        
        # 不在初始化时检查API密钥，而是在使用时检查
    
    def set_runtime_config(self, api_config: dict):
        """设置运行时配置"""
        if api_config:
            self.config = api_config
            self.api_key = self.config.get('api_key', '')
            self.base_url = (self.config.get('base_url') or 'https://api.siliconflow.cn/v1').rstrip('/')
            self.model = self.config.get('model', 'FunAudioLLM/SenseVoiceSmall')
    
    def transcribe_audio(self, audio_path: str, language: str = 'auto') -> Dict[str, Any]:
        """转录音频文件"""
        if not self.api_key:
            raise ValueError("硅基流动API密钥未配置")
            
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        max_retries = 3
        
        for retry in range(max_retries):
            try:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                }
                
                # 准备文件上传
                with open(audio_path, 'rb') as audio_file:
                    files = {
                        'file': ('audio.wav', audio_file, 'audio/wav')
                    }
                    
                    data = {
                        'model': self.model
                    }
                    
                    base = (self.base_url or 'https://api.siliconflow.cn/v1').rstrip('/')
                    response = requests.post(
                        f"{base}/audio/transcriptions",
                        headers=headers,
                        files=files,
                        data=data,
                        timeout=300  # 5分钟超时
                    )
                    
                    response.raise_for_status()
                    try:
                        result = response.json()
                    except ValueError:
                        # broader 兼容：某些 requests 版本抛 ValueError
                        if retry < max_retries - 1:
                            logger.warning(f"API返回格式错误，第 {retry+1} 次重试...")
                            time.sleep(2)
                            continue
                        else:
                            raise Exception("API返回格式错误")
                    
                    # 根据硅基流动API实际返回格式解析
                    text = result.get('text', '')
                    if not text and isinstance(result, dict):
                        # 如果text字段为空，尝试其他可能的字段名
                        text = result.get('transcription', '') or result.get('content', '')
                    
                    # 检查结果是否有效
                    if not text or len(text.strip()) == 0:
                        if retry < max_retries - 1:
                            logger.warning(f"音频文件返回空文本，第 {retry+1} 次重试...")
                            time.sleep(2)  # 重试前等待
                            continue
                        else:
                            logger.error(f"音频文件重试{max_retries}次后仍返回空文本")
                            raise Exception("语音转文字失败：API返回空文本")
                    
                    # 检查最小文本长度（避免只返回标点符号或单个字符）
                    if len(text.strip()) < 3:
                        if retry < max_retries - 1:
                            logger.warning(f"音频文件返回文本过短（{len(text.strip())}字符），第 {retry+1} 次重试...")
                            time.sleep(2)  # 重试前等待
                            continue
                        else:
                            logger.error(f"音频文件重试{max_retries}次后仍返回过短文本")
                            raise Exception(f"语音转文字失败：API返回文本过短（{len(text.strip())}字符）")
                    
                    # 硅基流动API不返回详细的时间戳信息，所以segments为空
                    return {
                        'text': text,
                        'segments': [],  # API不支持时间戳
                        'language': 'unknown',  # API不返回语言信息
                        'duration': 0  # API不返回时长信息
                    }
                    
            except requests.exceptions.RequestException as e:
                if retry < max_retries - 1:
                    logger.warning(f"API请求失败: {e}，第 {retry+1} 次重试...")
                    time.sleep(2)  # 重试前等待
                else:
                    raise Exception(f"语音转文字请求失败: {e}")
            except json.JSONDecodeError as e:
                # 兼容旧路径，实际已在上方 try/except ValueError 处理；保留以免行为变化
                if retry < max_retries - 1:
                    logger.warning(f"API返回格式错误，第 {retry+1} 次重试...")
                    time.sleep(2)
                else:
                    raise Exception("API返回格式错误")
        
        # 这里不会执行到，只是为了语法完整性
        raise Exception("转录失败")
    
        
    def format_transcript(self, transcription_results: List[Dict[str, Any]]) -> str:
        """格式化转录结果为逐字稿"""
        transcript = ""
        
        for result in transcription_results:
            if result.get('error'):
                transcript += f"\n[片段 {result['segment_index']+1} 处理失败: {result['error']}\n"
                continue
            
            # 直接添加文本，不包含时间戳
            text = result.get('text', '').strip()
            if text:
                transcript += text + "\n\n"
        
        return transcript
    
    
    def get_full_text(self, transcription_results: List[Dict[str, Any]]) -> str:
        """获取完整文本（无时间戳）"""
        full_text = ""
        
        for result in transcription_results:
            if not result.get('error') and result.get('text'):
                full_text += result['text'] + " "
        
        return full_text.strip()

if __name__ == "__main__":
    # 测试代码
    try:
        stt = SpeechToText()
        print("硅基流动语音转文字服务初始化成功")
    except Exception as e:
        print(f"初始化失败: {e}")
