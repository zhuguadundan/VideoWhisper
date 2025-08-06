import requests
import json
import time
import os
from typing import List, Dict, Any
from app.config.settings import Config

class SpeechToText:
    def __init__(self):
        self.config = Config.get_api_config('siliconflow')
        self.api_key = self.config.get('api_key', '')
        self.base_url = self.config.get('base_url', '')
        self.model = self.config.get('model', 'FunAudioLLM/SenseVoiceSmall')
        
        if not self.api_key:
            raise ValueError("硅基流动API密钥未配置")
    
    def transcribe_audio(self, audio_path: str, language: str = 'auto') -> Dict[str, Any]:
        """转录音频文件"""
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
        }
        
        # 准备文件上传
        with open(audio_path, 'rb') as audio_file:
            files = {
                'file': ('audio.wav', audio_file, 'audio/wav')
            }
            
            data = {
                'model': self.model,
                'response_format': 'verbose_json',  # 获取详细结果包含时间戳
                'language': language if language != 'auto' else None
            }
            
            try:
                response = requests.post(
                    f"{self.base_url}/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=300  # 5分钟超时
                )
                
                response.raise_for_status()
                result = response.json()
                
                return {
                    'text': result.get('text', ''),
                    'segments': result.get('segments', []),
                    'language': result.get('language', 'unknown'),
                    'duration': result.get('duration', 0)
                }
                
            except requests.exceptions.RequestException as e:
                raise Exception(f"语音转文字请求失败: {e}")
            except json.JSONDecodeError:
                raise Exception("API返回格式错误")
    
    def transcribe_audio_segments(self, segments: List[Dict]) -> List[Dict[str, Any]]:
        """转录音频片段列表"""
        results = []
        
        for i, segment in enumerate(segments):
            print(f"正在处理片段 {i+1}/{len(segments)}: {segment['path']}")
            
            try:
                result = self.transcribe_audio(segment['path'])
                
                # 调整时间戳
                adjusted_segments = []
                if result['segments']:
                    for seg in result['segments']:
                        adjusted_seg = seg.copy()
                        adjusted_seg['start'] += segment['start_time']
                        adjusted_seg['end'] += segment['start_time']
                        adjusted_segments.append(adjusted_seg)
                
                results.append({
                    'segment_index': segment['index'],
                    'text': result['text'],
                    'segments': adjusted_segments,
                    'start_time': segment['start_time'],
                    'end_time': segment['end_time'],
                    'language': result.get('language', 'unknown')
                })
                
                # 添加延迟避免API限制
                time.sleep(1)
                
            except Exception as e:
                print(f"片段 {i+1} 处理失败: {e}")
                results.append({
                    'segment_index': segment['index'],
                    'text': '',
                    'segments': [],
                    'start_time': segment['start_time'],
                    'end_time': segment['end_time'],
                    'error': str(e)
                })
        
        return results
    
    def format_transcript(self, transcription_results: List[Dict[str, Any]]) -> str:
        """格式化转录结果为逐字稿"""
        transcript = ""
        
        for result in transcription_results:
            if result.get('error'):
                transcript += f"\n[片段 {result['segment_index']+1} 处理失败: {result['error']}]\n"
                continue
            
            if result.get('segments'):
                for segment in result['segments']:
                    start_time = self._format_timestamp(segment.get('start', 0))
                    end_time = self._format_timestamp(segment.get('end', 0))
                    text = segment.get('text', '').strip()
                    
                    if text:
                        transcript += f"[{start_time} - {end_time}] {text}\n"
            else:
                # 如果没有详细片段，使用整体文本
                start_time = self._format_timestamp(result['start_time'])
                end_time = self._format_timestamp(result['end_time'])
                text = result.get('text', '').strip()
                
                if text:
                    transcript += f"[{start_time} - {end_time}] {text}\n"
        
        return transcript
    
    def _format_timestamp(self, seconds: float) -> str:
        """格式化时间戳为 HH:MM:SS 格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
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