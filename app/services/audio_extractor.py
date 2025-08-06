import ffmpeg
import os
from typing import Optional
from app.config.settings import Config

class AudioExtractor:
    def __init__(self):
        self.config = Config.load_config()
        self.temp_dir = self.config['system']['temp_dir']
        self.output_dir = self.config['system']['output_dir']
        self.audio_format = self.config['system']['audio_format']
        self.sample_rate = self.config['system']['audio_sample_rate']
        
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
    
    def extract_audio_from_video(self, video_path: str, output_path: Optional[str] = None) -> str:
        """从视频文件提取音频"""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        if not output_path:
            # 生成输出文件名
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(self.temp_dir, f"{base_name}.{self.audio_format}")
        
        try:
            # 使用ffmpeg提取音频
            (
                ffmpeg
                .input(video_path)
                .output(
                    output_path,
                    acodec='pcm_s16le',  # WAV格式
                    ar=self.sample_rate,  # 采样率
                    ac=1,  # 单声道
                    y=True  # 覆盖已存在的文件
                )
                .run(quiet=True, overwrite_output=True)
            )
            
            return output_path
            
        except ffmpeg.Error as e:
            raise Exception(f"音频提取失败: {e}")
    
    def convert_audio_format(self, input_path: str, output_path: str, 
                           target_format: str = 'wav', 
                           sample_rate: int = None) -> str:
        """转换音频格式"""
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"音频文件不存在: {input_path}")
        
        if not sample_rate:
            sample_rate = self.sample_rate
        
        try:
            stream = ffmpeg.input(input_path)
            
            if target_format.lower() == 'wav':
                stream = ffmpeg.output(
                    stream,
                    output_path,
                    acodec='pcm_s16le',
                    ar=sample_rate,
                    ac=1
                )
            elif target_format.lower() == 'mp3':
                stream = ffmpeg.output(
                    stream,
                    output_path,
                    acodec='mp3',
                    ar=sample_rate,
                    ab='192k'
                )
            else:
                stream = ffmpeg.output(stream, output_path, ar=sample_rate)
            
            ffmpeg.run(stream, quiet=True, overwrite_output=True)
            return output_path
            
        except ffmpeg.Error as e:
            raise Exception(f"音频格式转换失败: {e}")
    
    def split_audio_by_duration(self, input_path: str, segment_duration: int = 300) -> list:
        """按时长分割音频文件"""
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"音频文件不存在: {input_path}")
        
        # 获取音频时长
        probe = ffmpeg.probe(input_path)
        duration = float(probe['streams'][0]['duration'])
        
        segments = []
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        
        try:
            current_time = 0
            segment_index = 0
            
            while current_time < duration:
                end_time = min(current_time + segment_duration, duration)
                segment_path = os.path.join(
                    self.temp_dir, 
                    f"{base_name}_segment_{segment_index:03d}.{self.audio_format}"
                )
                
                (
                    ffmpeg
                    .input(input_path, ss=current_time, t=end_time - current_time)
                    .output(segment_path, acodec='pcm_s16le', ar=self.sample_rate, ac=1)
                    .run(quiet=True, overwrite_output=True)
                )
                
                segments.append({
                    'path': segment_path,
                    'start_time': current_time,
                    'end_time': end_time,
                    'index': segment_index
                })
                
                current_time = end_time
                segment_index += 1
            
            return segments
            
        except ffmpeg.Error as e:
            raise Exception(f"音频分割失败: {e}")
    
    def get_audio_info(self, audio_path: str) -> dict:
        """获取音频文件信息"""
        try:
            probe = ffmpeg.probe(audio_path)
            audio_stream = next((stream for stream in probe['streams'] 
                               if stream['codec_type'] == 'audio'), None)
            
            if not audio_stream:
                raise Exception("无法找到音频流")
            
            return {
                'duration': float(probe['format']['duration']),
                'sample_rate': int(audio_stream['sample_rate']),
                'channels': audio_stream['channels'],
                'codec': audio_stream['codec_name'],
                'bitrate': int(probe['format'].get('bit_rate', 0)),
                'size': int(probe['format']['size'])
            }
            
        except Exception as e:
            raise Exception(f"获取音频信息失败: {e}")

if __name__ == "__main__":
    # 测试代码
    extractor = AudioExtractor()
    print("AudioExtractor 初始化成功")