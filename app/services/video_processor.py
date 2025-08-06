import os
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from app.models.data_models import ProcessingTask, VideoInfo, TranscriptionResult, TranscriptionSegment
from app.services.video_downloader import VideoDownloader
from app.services.audio_extractor import AudioExtractor
from app.services.speech_to_text import SpeechToText
from app.services.text_processor import TextProcessor
from app.config.settings import Config

class VideoProcessor:
    """视频处理核心类"""
    
    def __init__(self):
        self.config = Config.load_config()
        # 处理相对路径，转换为绝对路径
        output_dir = self.config['system']['output_dir']
        if not os.path.isabs(output_dir):
            # 如果是相对路径，基于项目根目录
            self.output_dir = os.path.abspath(output_dir)
        else:
            self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 初始化服务
        self.video_downloader = VideoDownloader()
        self.audio_extractor = AudioExtractor()
        self.speech_to_text = SpeechToText()
        self.text_processor = TextProcessor()
        
        # 存储处理任务
        self.tasks: Dict[str, ProcessingTask] = {}
        self.tasks_file = os.path.join(self.output_dir, 'tasks.json')
        
        # 加载已有任务数据
        self.load_tasks_from_disk()
    
    def create_task(self, video_url: str) -> str:
        """创建新的处理任务"""
        task_id = str(uuid.uuid4())
        task = ProcessingTask(id=task_id, video_url=video_url)
        self.tasks[task_id] = task
        self.save_tasks_to_disk()
        return task_id
    
    def get_task(self, task_id: str) -> Optional[ProcessingTask]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def process_video(self, task_id: str, llm_provider: str = 'openai') -> ProcessingTask:
        """处理视频的完整流程"""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        try:
            task.status = "processing"
            task.progress = 0
            self.save_tasks_to_disk()  # 保存状态更新
            
            # 1. 获取视频信息
            print(f"[{task_id}] 获取视频信息...")
            video_info_dict = self.video_downloader.get_video_info(task.video_url)
            task.video_info = VideoInfo(
                title=video_info_dict['title'],
                url=video_info_dict['url'],
                duration=video_info_dict['duration'],
                uploader=video_info_dict['uploader']
            )
            task.progress = 10
            
            # 2. 下载音频
            print(f"[{task_id}] 下载音频...")
            audio_path = self.video_downloader.download_audio_only(task.video_url)
            task.progress = 30
            
            # 3. 处理长音频（分段）
            print(f"[{task_id}] 处理音频...")
            audio_info = self.audio_extractor.get_audio_info(audio_path)
            
            if audio_info['duration'] > 300:  # 超过5分钟分段处理
                segments = self.audio_extractor.split_audio_by_duration(audio_path, 300)
                task.progress = 40
                
                # 4. 语音转文字
                print(f"[{task_id}] 语音转文字...")
                transcription_results = self.speech_to_text.transcribe_audio_segments(segments)
                
                # 合并结果
                all_segments = []
                full_text = ""
                for result in transcription_results:
                    if not result.get('error'):
                        full_text += result.get('text', '') + " "
                        for seg in result.get('segments', []):
                            all_segments.append(TranscriptionSegment(
                                text=seg.get('text', ''),
                                start_time=seg.get('start', 0),
                                end_time=seg.get('end', 0),
                                confidence=seg.get('confidence', 0.0)
                            ))
                
                # 清理分段文件
                for segment in segments:
                    try:
                        os.remove(segment['path'])
                    except:
                        pass
            else:
                # 直接处理短音频
                transcription_result = self.speech_to_text.transcribe_audio(audio_path)
                full_text = transcription_result['text']
                all_segments = [
                    TranscriptionSegment(
                        text=seg.get('text', ''),
                        start_time=seg.get('start', 0),
                        end_time=seg.get('end', 0),
                        confidence=seg.get('confidence', 0.0)
                    ) for seg in transcription_result.get('segments', [])
                ]
            
            task.transcription = TranscriptionResult(
                segments=all_segments,
                full_text=full_text.strip(),
                language=transcription_results[0].get('language', 'unknown') if transcription_results else 'unknown',
                duration=audio_info['duration']
            )
            task.progress = 60
            
            # 5. 生成格式化逐字稿
            print(f"[{task_id}] 生成逐字稿...")
            task.transcript = self.text_processor.generate_transcript(
                task.transcription.full_text, 
                provider=llm_provider
            )
            task.progress = 80
            
            # 6. 生成总结报告
            print(f"[{task_id}] 生成总结报告...")
            task.summary = self.text_processor.generate_summary(
                task.transcript,
                provider=llm_provider
            )
            task.progress = 90
            
            # 7. 内容分析
            print(f"[{task_id}] 内容分析...")
            task.analysis = self.text_processor.analyze_content(
                task.transcript,
                provider=llm_provider
            )
            task.progress = 95
            
            # 8. 保存结果
            self._save_results(task)
            task.progress = 100
            task.status = "completed"
            
            # 清理临时文件
            try:
                os.remove(audio_path)
            except:
                pass
            
            print(f"[{task_id}] 处理完成!")
            
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            print(f"[{task_id}] 处理失败: {e}")
        
        # 保存任务状态到磁盘
        self.save_tasks_to_disk()
        return task
    
    def _save_results(self, task: ProcessingTask):
        """保存处理结果"""
        task_dir = os.path.join(self.output_dir, task.id)
        os.makedirs(task_dir, exist_ok=True)
        
        # 保存逐字稿
        transcript_path = os.path.join(task_dir, 'transcript.txt')
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(task.transcript)
        
        # 保存带时间戳的逐字稿
        if task.transcription and task.transcription.segments:
            timestamped_path = os.path.join(task_dir, 'transcript_with_timestamps.txt')
            with open(timestamped_path, 'w', encoding='utf-8') as f:
                for segment in task.transcription.segments:
                    start_time = self._format_timestamp(segment.start_time)
                    end_time = self._format_timestamp(segment.end_time)
                    f.write(f"[{start_time} - {end_time}] {segment.text}\n")
        
        # 保存总结报告
        summary_path = os.path.join(task_dir, 'summary.md')
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(f"# {task.video_info.title if task.video_info else '视频总结报告'}\n\n")
            f.write(f"**视频URL:** {task.video_url}\n")
            if task.video_info:
                f.write(f"**上传者:** {task.video_info.uploader}\n")
                f.write(f"**时长:** {self._format_timestamp(task.video_info.duration)}\n")
            f.write(f"**处理时间:** {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            if task.summary.get('brief_summary'):
                f.write("## 简要摘要\n\n")
                f.write(task.summary['brief_summary'] + "\n\n")
            
            if task.summary.get('detailed_summary'):
                f.write(task.summary['detailed_summary'] + "\n\n")
            
            if task.summary.get('keywords'):
                f.write("## 关键词\n\n")
                f.write(task.summary['keywords'] + "\n\n")
        
        # 保存完整数据（JSON格式）
        data_path = os.path.join(task_dir, 'data.json')
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(task.to_dict(), f, ensure_ascii=False, indent=2)
    
    def _format_timestamp(self, seconds: float) -> str:
        """格式化时间戳"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def get_task_progress(self, task_id: str) -> Dict[str, Any]:
        """获取任务进度"""
        task = self.get_task(task_id)
        if not task:
            return {"error": "任务不存在"}
        
        return {
            "id": task.id,
            "status": task.status,
            "progress": task.progress,
            "video_title": task.video_info.title if task.video_info else "",
            "error_message": task.error_message
        }
    
    def load_tasks_from_disk(self):
        """从磁盘加载任务数据"""
        try:
            if os.path.exists(self.tasks_file):
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    tasks_data = json.load(f)
                
                for task_data in tasks_data:
                    task = ProcessingTask(
                        id=task_data['id'],
                        video_url=task_data['video_url'],
                        status=task_data['status'],
                        created_at=datetime.fromisoformat(task_data['created_at']),
                        transcript=task_data.get('transcript', ''),
                        summary=task_data.get('summary', {}),
                        analysis=task_data.get('analysis', {}),
                        error_message=task_data.get('error_message', ''),
                        progress=task_data.get('progress', 0)
                    )
                    
                    # 恢复视频信息
                    if task_data.get('video_info'):
                        vi = task_data['video_info']
                        task.video_info = VideoInfo(
                            title=vi.get('title', ''),
                            url=vi.get('url', task_data['video_url']),
                            duration=vi.get('duration', 0),
                            uploader=vi.get('uploader', '')
                        )
                    
                    self.tasks[task.id] = task
                    
                print(f"已加载 {len(self.tasks)} 个历史任务")
        except Exception as e:
            print(f"加载任务数据失败: {e}")
    
    def save_tasks_to_disk(self):
        """保存任务数据到磁盘"""
        try:
            tasks_data = [task.to_dict() for task in self.tasks.values()]
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存任务数据失败: {e}")