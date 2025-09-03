import ffmpeg
import os
import re
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
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符，适配Windows系统"""
        # Windows禁用字符: < > : " | ? * \ /
        illegal_chars = r'[<>:"|?*\\\\/]'
        
        # 替换非法字符为下划线
        sanitized = re.sub(illegal_chars, '_', filename)
        
        # 移除开头结尾的空格和点号（Windows特殊要求）
        sanitized = sanitized.strip(' .')
        
        # 限制长度避免路径过长问题
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        
        # 如果清理后为空，使用默认名称
        if not sanitized:
            sanitized = 'audio_file'
            
        return sanitized
    
    def extract_audio_from_video(self, video_path: str, output_path: Optional[str] = None) -> str:
        """从视频文件提取音频"""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        if not output_path:
            # 生成输出文件名 - 清理非法字符
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            safe_base_name = self._sanitize_filename(base_name)
            output_path = os.path.join(self.temp_dir, f"{safe_base_name}.{self.audio_format}")
        
        try:
            # 使用ffmpeg提取音频
            (
                ffmpeg
                .input(video_path)
                .output(
                    output_path,
                    acodec='pcm_s16le',  # WAV格式
                    ar=self.sample_rate,  # 采样率
                    ac=1  # 单声道
                )
                .run(overwrite_output=True)  # 移除y=True，使用overwrite_output=True代替
            )
            
            return output_path
            
        except ffmpeg.Error as e:
            # 提供更详细的错误信息
            stderr_output = e.stderr.decode('utf-8') if e.stderr else 'No stderr output'
            raise Exception(f"音频提取失败: ffmpeg error (see stderr output for detail)\nStderr: {stderr_output}")
    
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
        print(f"[DEBUG] split_audio_by_duration: input_path={input_path}, segment_duration={segment_duration}")
        
        if not os.path.exists(input_path):
            print(f"[ERROR] 输入音频文件不存在: {input_path}")
            raise FileNotFoundError(f"音频文件不存在: {input_path}")
        
        # 获取音频时长
        try:
            print(f"[DEBUG] 开始探测音频信息...")
            probe = ffmpeg.probe(input_path)
            duration = float(probe['streams'][0]['duration'])
            print(f"[DEBUG] 音频时长: {duration}秒")
        except Exception as probe_error:
            print(f"[ERROR] 探测音频信息失败: {probe_error}")
            raise Exception(f"探测音频信息失败: {probe_error}")
        
        segments = []
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        print(f"[DEBUG] 原始基础文件名: {base_name}")
        # 清理基础文件名中的非法字符
        safe_base_name = self._sanitize_filename(base_name)
        print(f"[DEBUG] 清理后基础文件名: {safe_base_name}")
        
        try:
            current_time = 0
            segment_index = 0
            
            while current_time < duration:
                end_time = min(current_time + segment_duration, duration)
                segment_filename = f"{safe_base_name}_segment_{segment_index:03d}.{self.audio_format}"
                segment_path = os.path.join(self.temp_dir, segment_filename)
                
                print(f"[DEBUG] 创建分段 {segment_index}: {segment_path}")
                print(f"[DEBUG] 时间范围: {current_time:.2f}s - {end_time:.2f}s")
                
                try:
                    (
                        ffmpeg
                        .input(input_path, ss=current_time, t=end_time - current_time)
                        .output(segment_path, acodec='pcm_s16le', ar=self.sample_rate, ac=1)
                        .run(quiet=True, overwrite_output=True)
                    )
                    print(f"[DEBUG] 分段 {segment_index} 创建成功")
                    
                    # 验证文件是否真的创建了
                    if os.path.exists(segment_path):
                        file_size = os.path.getsize(segment_path)
                        print(f"[DEBUG] 分段文件大小: {file_size} bytes")
                    else:
                        print(f"[ERROR] 分段文件不存在: {segment_path}")
                        raise Exception(f"分段文件创建失败: {segment_path}")
                        
                except Exception as segment_error:
                    print(f"[ERROR] 创建分段 {segment_index} 失败: {segment_error}")
                    print(f"[ERROR] 错误类型: {type(segment_error)}")
                    raise Exception(f"创建分段失败: {segment_error}")
                
                segments.append({
                    'path': segment_path,
                    'start_time': current_time,
                    'end_time': end_time,
                    'index': segment_index
                })
                
                current_time = end_time
                segment_index += 1
            
            print(f"[DEBUG] 音频分割完成，共创建 {len(segments)} 个分段")
            return segments
            
        except Exception as e:
            print(f"[ERROR] 音频分割过程失败: {e}")
            print(f"[ERROR] 错误类型: {type(e)}")
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