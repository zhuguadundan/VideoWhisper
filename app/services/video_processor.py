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
        
        # 添加临时目录配置
        temp_dir = self.config['system']['temp_dir']
        if not os.path.isabs(temp_dir):
            self.temp_dir = os.path.abspath(temp_dir)
        else:
            self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)
        
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
    
    def process_video(self, task_id: str, llm_provider: str = None, api_config: dict = None) -> ProcessingTask:
        """处理视频的完整流程"""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        try:
            # 如果传入了api_config，临时设置配置
            if api_config:
                print(f"[{task_id}] 使用前端传递的API配置")
                # 临时更新speech_to_text和text_processor的配置
                if hasattr(self.speech_to_text, 'set_runtime_config'):
                    self.speech_to_text.set_runtime_config(api_config.get('siliconflow', {}))
                if hasattr(self.text_processor, 'set_runtime_config'):
                    self.text_processor.set_runtime_config(api_config.get('text_processor', {}))
            
            # 检查文本处理器是否有可用的提供商
            available_providers = self.text_processor.get_available_providers()
            if not available_providers:
                task.status = "failed"
                task.error_message = "没有可用的AI文本处理服务提供商，请先在设置页面配置API密钥"
                self.save_tasks_to_disk()
                return task
            
            # 如果指定的provider不可用，使用默认provider
            if not llm_provider or not self.text_processor.is_provider_available(llm_provider):
                llm_provider = self.text_processor.get_default_provider()
                print(f"[{task_id}] 使用默认AI提供商: {llm_provider}")
            else:
                print(f"[{task_id}] 使用指定AI提供商: {llm_provider}")
            
            task.status = "processing"
            task.progress = 0
            task.progress_stage = "获取视频信息"
            task.progress_detail = "正在解析视频链接..."
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
            task.progress_detail = f"视频时长: {self._format_timestamp(video_info_dict['duration'])}"
            task.estimated_time = int(video_info_dict['duration'] * 0.3)  # 粗略估计处理时间
            
            # 2. 下载音频
            print(f"[{task_id}] 下载音频...")
            task.progress_stage = "下载音频"
            task.progress_detail = "正在从视频中提取音频..."
            self.save_tasks_to_disk()
            audio_path = self.video_downloader.download_audio_only(task.video_url)
            task.progress = 30
            
            # 3. 处理长音频（分段）
            print(f"[{task_id}] 处理音频...")
            task.progress_stage = "处理音频"
            task.progress_detail = "分析音频文件..."
            self.save_tasks_to_disk()
            audio_info = self.audio_extractor.get_audio_info(audio_path)
            
            if audio_info['duration'] > 300:  # 超过5分钟分段处理
                segments = self.audio_extractor.split_audio_by_duration(audio_path, 300)
                task.progress = 40
                task.total_segments = len(segments)
                task.progress_detail = f"音频已分割为 {len(segments)} 个片段"
                self.save_tasks_to_disk()
                
                # 4. 语音转文字
                print(f"[{task_id}] 语音转文字...")
                task.progress_stage = "语音转文字"
                transcription_results = []
                
                for i, segment in enumerate(segments):
                    task.processed_segments = i + 1
                    task.progress_detail = f"正在处理第 {i+1}/{len(segments)} 个音频片段..."
                    progress_increment = (60 - 40) * (i + 1) / len(segments)
                    task.progress = 40 + int(progress_increment)
                    self.save_tasks_to_disk()
                    
                    try:
                        segment_result = self.speech_to_text.transcribe_audio_segments([segment])
                        if segment_result:
                            transcription_results.extend(segment_result)
                        print(f"[{task_id}] 片段 {i+1} 处理成功")
                    except Exception as e:
                        print(f"[{task_id}] 片段 {i+1} 处理失败: {e}")
                        # 添加空的结果占位符，保持顺序
                        transcription_results.append({
                            'segment_index': i,
                            'text': '',
                            'segments': [],
                            'start_time': segment['start_time'],
                            'end_time': segment['end_time'],
                            'error': str(e)
                        })
                
                task.progress = 60
                
                # 合并结果 - 按时间顺序排序
                transcription_results.sort(key=lambda x: x.get('segment_index', 0))
                
                all_segments = []
                full_text = ""
                successful_segments = 0
                
                for result in transcription_results:
                    if not result.get('error'):
                        successful_segments += 1
                        text = result.get('text', '').strip()
                        if text:
                            full_text += text + " "
                        
                        # 处理详细片段信息
                        for seg in result.get('segments', []):
                            all_segments.append(TranscriptionSegment(
                                text=seg.get('text', ''),
                                start_time=seg.get('start', 0),
                                end_time=seg.get('end', 0),
                                confidence=seg.get('confidence', 0.0)
                            ))
                    else:
                        print(f"[{task_id}] 跳过失败片段 {result.get('segment_index', '未知')}: {result.get('error', '未知错误')}")
                
                print(f"[{task_id}] 成功处理 {successful_segments}/{len(segments)} 个片段")
                
                # 如果没有成功的片段，抛出异常
                if successful_segments == 0:
                    raise Exception("所有音频片段处理失败")
                
                # 清理分段文件
                for segment in segments:
                    try:
                        if os.path.exists(segment['path']):
                            os.remove(segment['path'])
                    except Exception as e:
                        print(f"[{task_id}] 清理临时文件失败: {e}")
                
                # 设置语言信息
                language = 'unknown'
                for result in transcription_results:
                    if not result.get('error') and result.get('language'):
                        language = result['language']
                        break
            else:
                # 直接处理短音频
                task.progress_stage = "语音转文字"
                task.progress_detail = "处理短音频文件..."
                task.total_segments = 1
                task.processed_segments = 1
                self.save_tasks_to_disk()
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
                language = transcription_result.get('language', 'unknown')
            
            # 创建转录结果对象
            print(f"[{task_id}] 合并转录结果: 文本长度={len(full_text)}, 片段数={len(all_segments)}")
            task.transcription = TranscriptionResult(
                segments=all_segments,
                full_text=full_text.strip(),
                language=language,
                duration=audio_info['duration']
            )
            task.progress = 60
            
            # 5. 生成格式化逐字稿
            print(f"[{task_id}] 生成逐字稿...")
            task.progress_stage = "生成逐字稿"
            task.progress_detail = "使用AI优化文本格式..."
            self.save_tasks_to_disk()
            task.transcript = self.text_processor.generate_transcript(
                task.transcription.full_text, 
                provider=llm_provider
            )
            task.progress = 80
            
            # 6. 生成总结报告
            print(f"[{task_id}] 生成总结报告...")
            task.progress_stage = "生成总结报告"
            task.progress_detail = "AI正在分析内容并生成摘要..."
            self.save_tasks_to_disk()
            task.summary = self.text_processor.generate_summary(
                task.transcript,
                provider=llm_provider
            )
            task.progress = 90
            
            # 7. 内容分析
            print(f"[{task_id}] 内容分析...")
            task.progress_stage = "内容分析"
            task.progress_detail = "提取关键信息和主题..."
            self.save_tasks_to_disk()
            task.analysis = self.text_processor.analyze_content(
                task.transcript,
                provider=llm_provider
            )
            task.progress = 95
            
            # 8. 保存结果
            task.progress_stage = "保存结果"
            task.progress_detail = "生成输出文件..."
            self.save_tasks_to_disk()
            self._save_results(task)
            task.progress = 100
            task.status = "completed"
            task.progress_stage = "完成"
            task.progress_detail = "处理完成！"
            task.estimated_time = 0
            
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
            "progress_stage": task.progress_stage,
            "progress_detail": task.progress_detail,
            "estimated_time": task.estimated_time,
            "processed_segments": task.processed_segments,
            "total_segments": task.total_segments,
            "video_title": task.video_info.title if task.video_info else "",
            "video_duration": task.video_info.duration if task.video_info else 0,
            "error_message": task.error_message
        }
    
    def load_tasks_from_disk(self):
        """从磁盘加载任务数据"""
        try:
            if os.path.exists(self.tasks_file):
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    tasks_data = json.load(f)
                
                # 过滤掉未完成的任务（只加载已完成或失败的任务）
                completed_tasks = []
                for task_data in tasks_data:
                    # 将未完成的任务标记为失败
                    if task_data['status'] == 'processing':
                        task_data['status'] = 'failed'
                        task_data['error_message'] = '程序重启导致任务中断'
                        task_data['progress'] = 0
                    
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
                    completed_tasks.append(task_data)
                
                # 重新保存清理后的任务数据
                if len(completed_tasks) != len(tasks_data):
                    with open(self.tasks_file, 'w', encoding='utf-8') as f:
                        json.dump(completed_tasks, f, ensure_ascii=False, indent=2)
                    print(f"已清理未完成任务，加载 {len(self.tasks)} 个历史任务")
                else:
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