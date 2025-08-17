import os
import json
import uuid
import glob
import re
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
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
    
    def create_task(self, video_url: str, youtube_cookies: str = None) -> str:
        """创建新的处理任务 - 简化版"""
        task_id = str(uuid.uuid4())
        task = ProcessingTask(id=task_id, video_url=video_url)
        
        # 如果提供了 cookies，存储到任务中
        if youtube_cookies:
            task.youtube_cookies = youtube_cookies
            
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
            video_info_dict = self.video_downloader.get_video_info(task.video_url, task.youtube_cookies)
            task.video_info = VideoInfo(
                title=video_info_dict['title'],
                url=video_info_dict['url'],
                duration=video_info_dict['duration'],
                uploader=video_info_dict['uploader']
            )
            task.progress = 10
            task.progress_detail = f"视频时长: {self._format_duration(video_info_dict['duration'])}"
            task.estimated_time = int(video_info_dict['duration'] * 0.3)  # 粗略估计处理时间
            
            # 2. 下载音频（简化版，仅音频下载）
            print(f"[{task_id}] 下载音频...")
            task.progress_stage = "下载音频"
            task.progress_detail = "正在下载音频文件..."
            self.save_tasks_to_disk()
            
            audio_path = self.video_downloader.download_audio_only(task.video_url, task.id, cookies_str=task.youtube_cookies)
            task.audio_file_path = audio_path
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
                
                # 增加连续失败检测
                consecutive_failures = 0
                max_consecutive_failures = 3  # 最多允许连续失败3个片段
                
                for i, segment in enumerate(segments):
                    task.processed_segments = i + 1
                    task.progress_detail = f"正在处理第 {i+1}/{len(segments)} 个音频片段..."
                    progress_increment = (60 - 40) * (i + 1) / len(segments)
                    task.progress = 40 + int(progress_increment)
                    self.save_tasks_to_disk()
                    
                    try:
                        # 直接调用transcribe_audio处理单个片段
                        segment_result = self.speech_to_text.transcribe_audio(segment['path'])
                        
                        # 验证结果文本
                        text = segment_result.get('text', '').strip()
                        if not text or len(text) < 3:
                            raise Exception(f"转录文本无效: 长度={len(text)}")
                        
                        # 构建标准化的结果格式
                        transcription_results.append({
                            'segment_index': segment['index'],
                            'text': text,
                            'segments': segment_result.get('segments', []),
                            'start_time': segment['start_time'],
                            'end_time': segment['end_time'],
                            'language': segment_result.get('language', 'unknown')
                        })
                        print(f"[{task_id}] 片段 {i+1} 处理成功: 文本长度={len(text)}")
                        
                        # 重置连续失败计数器
                        consecutive_failures = 0
                        
                        # 成功后添加延迟避免API限制
                        time.sleep(1)
                        
                    except Exception as e:
                        consecutive_failures += 1
                        print(f"[{task_id}] 片段 {i+1} 处理失败: {e} (连续失败次数: {consecutive_failures})")
                        
                        # 添加空的结果占位符，保持顺序
                        transcription_results.append({
                            'segment_index': segment['index'],
                            'text': '',
                            'segments': [],
                            'start_time': segment['start_time'],
                            'end_time': segment['end_time'],
                            'error': str(e)
                        })
                        
                        # 检查连续失败次数
                        if consecutive_failures >= max_consecutive_failures:
                            print(f"[{task_id}] 连续失败次数达到上限 ({max_consecutive_failures})，停止处理")
                            # 计算当前片段索引
                            remaining_segments = len(segments) - (i + 1)
                            if remaining_segments > 0:
                                print(f"[{task_id}] 跳过剩余 {remaining_segments} 个片段")
                            break
                        
                        # 失败后也添加延迟，避免频繁调用API
                        time.sleep(2)
                
                task.progress = 60
                
                # 合并结果 - 按时间顺序排序
                transcription_results.sort(key=lambda x: x.get('segment_index', 0))
                
                all_segments = []
                full_text = ""
                successful_segments = 0
                failed_segments = 0
                processed_segments_count = len(transcription_results)  # 实际处理的片段数（可能因连续失败而提前终止）
                
                for result in transcription_results:
                    if not result.get('error'):
                        text = result.get('text', '').strip()
                        if text and len(text) >= 3:  # 只统计有效文本
                            successful_segments += 1
                            full_text += text + " "
                        else:
                            print(f"[{task_id}] 警告: 片段 {result.get('segment_index', '未知')} 返回无效文本")
                        
                        # 处理详细片段信息
                        for seg in result.get('segments', []):
                            all_segments.append(TranscriptionSegment(
                                text=seg.get('text', ''),
                                confidence=seg.get('confidence', 0.0)
                            ))
                    else:
                        failed_segments += 1
                        print(f"[{task_id}] 片段 {result.get('segment_index', '未知')} 处理失败: {result.get('error', '未知错误')}")
                
                print(f"[{task_id}] 处理统计: 成功 {successful_segments}/{processed_segments_count} 个片段, 失败 {failed_segments} 个片段")
                
                # 如果有剩余片段未处理（因连续失败而提前终止），给出提示
                if processed_segments_count < len(segments):
                    remaining_segments = len(segments) - processed_segments_count
                    print(f"[{task_id}] 跳过未处理片段: {remaining_segments} 个 (因连续失败而提前终止)")
                
                # 如果没有成功的片段，抛出异常
                if successful_segments == 0:
                    raise Exception(f"所有音频片段处理失败，共处理 {processed_segments_count} 个片段")
                
                # 计算实际处理的成功率（基于实际处理的片段数）
                success_rate = successful_segments / processed_segments_count if processed_segments_count > 0 else 0
                if success_rate < 0.8:
                    print(f"[{task_id}] 警告: 片段成功率较低 ({success_rate:.1%}), 可能会影响转录完整性")
                
                # 如果整体成功率过低（考虑未处理的片段），给出额外警告
                overall_success_rate = successful_segments / len(segments)
                if overall_success_rate < 0.5:
                    print(f"[{task_id}] 严重警告: 整体成功率过低 ({overall_success_rate:.1%}), 建议检查网络连接和API配置")
                
                # 分段文件清理由智能清理系统统一管理，这里不再立即删除
                print(f"[{task_id}] 分段音频文件将由智能清理系统管理")
                
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
                
                # 使用重试机制处理短音频（与长音频片段处理保持一致）
                max_retries = 3
                transcription_result = None
                
                for retry in range(max_retries):
                    try:
                        transcription_result = self.speech_to_text.transcribe_audio(audio_path)
                        
                        # 验证结果文本（与长音频处理逻辑一致）
                        text = transcription_result.get('text', '').strip()
                        if not text or len(text) < 3:
                            if retry < max_retries - 1:
                                print(f"[{task_id}] 短音频返回无效文本（长度={len(text)}），第 {retry+1} 次重试...")
                                time.sleep(2)
                                continue
                            else:
                                raise Exception(f"短音频处理重试{max_retries}次后仍返回无效文本")
                        
                        print(f"[{task_id}] 短音频处理成功: 文本长度={len(text)}")
                        break
                        
                    except Exception as e:
                        if retry < max_retries - 1:
                            print(f"[{task_id}] 短音频处理失败: {e}，第 {retry+1} 次重试...")
                            time.sleep(2)
                        else:
                            raise Exception(f"短音频处理重试{max_retries}次后仍然失败: {e}")
                
                if not transcription_result or not transcription_result.get('text'):
                    raise Exception("短音频处理失败：无法获取转录文本")
                
                full_text = transcription_result['text'].strip()
                # 硅基流动API不支持时间戳，所以创建基本的分段信息
                all_segments = [
                    TranscriptionSegment(
                        text=full_text,
                        start_time=0,
                        end_time=audio_info['duration'],
                        confidence=0.8  # 默认置信度
                    )
                ]
                language = transcription_result.get('language', 'unknown')
                
                print(f"[{task_id}] 短音频处理完成: 文本长度={len(full_text)}")
                
                # 统一延迟策略：短音频处理成功后也添加延迟
                time.sleep(1)
            
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
            task.ai_start_time = time.time()
            self.save_tasks_to_disk()
            
            start_time = time.time()
            task.transcript = self.text_processor.generate_transcript(
                task.transcription.full_text, 
                provider=llm_provider
            )
            ai_response_time = time.time() - start_time
            task.ai_response_times = getattr(task, 'ai_response_times', {})
            task.ai_response_times['transcript'] = ai_response_time
            task.progress = 70
            task.progress_detail = f"逐字稿生成完成 (耗时 {ai_response_time:.1f}s)"
            
            # 立即显示逐字稿给用户
            task.transcript_ready = True
            self.save_tasks_to_disk()
            
            # 6. 生成总结报告
            print(f"[{task_id}] 生成总结报告...")
            task.progress_stage = "生成总结报告"
            task.progress_detail = f"AI正在分析内容并生成摘要... (使用 {llm_provider})"
            self.save_tasks_to_disk()
            
            start_time = time.time()
            task.summary = self.text_processor.generate_summary(
                task.transcript,
                provider=llm_provider
            )
            ai_response_time = time.time() - start_time
            task.ai_response_times['summary'] = ai_response_time
            task.progress = 85
            task.progress_detail = f"摘要生成完成 (耗时 {ai_response_time:.1f}s)"
            self.save_tasks_to_disk()
            
            # 7. 内容分析
            print(f"[{task_id}] 内容分析...")
            task.progress_stage = "内容分析"
            task.progress_detail = f"提取关键信息和主题... (使用 {llm_provider})"
            self.save_tasks_to_disk()
            
            start_time = time.time()
            task.analysis = self.text_processor.analyze_content(
                task.transcript,
                provider=llm_provider
            )
            ai_response_time = time.time() - start_time
            task.ai_response_times['analysis'] = ai_response_time
            task.progress = 95
            task.progress_detail = f"内容分析完成 (耗时 {ai_response_time:.1f}s)"
            self.save_tasks_to_disk()
            
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
            
            # 清理临时文件 - 智能保留最近3次任务的文件
            self._smart_cleanup_temp_files(task_id, audio_path)
            
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
        
        # 保存逐字稿 (改为Markdown格式)
        transcript_path = os.path.join(task_dir, 'transcript.md')
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(f"# {task.video_info.title if task.video_info else '视频逐字稿'}\n\n")
            f.write(f"**视频URL:** {task.video_url}\n\n")
            if task.video_info:
                if task.video_info.uploader:
                    f.write(f"**UP主:** {task.video_info.uploader}\n")
                if task.video_info.duration:
                    duration = self._format_duration(task.video_info.duration)
                    f.write(f"**时长:** {duration}\n")
            f.write(f"**处理时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            f.write(task.transcript)
        
        
        # 保存总结报告
        summary_path = os.path.join(task_dir, 'summary.md')
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(f"# {task.video_info.title if task.video_info else '视频总结报告'}\n\n")
            f.write(f"**视频URL:** {task.video_url}\n")
            if task.video_info:
                f.write(f"**上传者:** {task.video_info.uploader}\n")
                f.write(f"**时长:** {self._format_duration(task.video_info.duration)}\n")
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
    
    def _format_duration(self, seconds: float) -> str:
        """格式化时长显示"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def get_task_progress(self, task_id: str) -> Dict[str, Any]:
        """获取任务进度"""
        task = self.get_task(task_id)
        if not task:
            return {"error": "任务不存在"}
        
        progress_info = {
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
            "error_message": task.error_message,
            "ai_response_times": getattr(task, 'ai_response_times', {}),
            "transcript_ready": getattr(task, 'transcript_ready', False)
        }
        
        # 如果逐字稿已准备好，包含逐字稿内容
        if getattr(task, 'transcript_ready', False) and task.transcript:
            progress_info["transcript_preview"] = task.transcript[:500] + "..." if len(task.transcript) > 500 else task.transcript
            progress_info["full_transcript"] = task.transcript
        
        return progress_info
    
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
    
    def _smart_cleanup_temp_files(self, current_task_id: str, current_audio_path: str):
        """智能清理临时文件，保留最近3次任务的文件"""
        try:
            # 1. 获取所有已完成的任务，按创建时间排序
            completed_tasks = [
                task for task in self.tasks.values() 
                if task.status == "completed"
            ]
            completed_tasks.sort(key=lambda x: x.created_at, reverse=True)
            
            # 2. 保留最近3次任务的ID（包括当前任务）
            keep_task_ids = {current_task_id}  # 当前任务ID
            for i, task in enumerate(completed_tasks[:3]):  # 最近3次完成的任务
                keep_task_ids.add(task.id)
            
            print(f"[{current_task_id}] 临时文件清理：保留任务 {keep_task_ids}")
            
            # 3. 获取临时目录下所有文件
            if not os.path.exists(self.temp_dir):
                return
                
            temp_files = os.listdir(self.temp_dir)
            files_to_delete = []
            files_to_keep = []
            
            for file_name in temp_files:
                file_path = os.path.join(self.temp_dir, file_name)
                if not os.path.isfile(file_path):
                    continue
                    
                # 4. 判断文件是否应该保留
                should_keep = False
                
                # 检查文件是否属于要保留的任务
                for task_id in keep_task_ids:
                    if self._is_file_related_to_task(file_name, task_id):
                        should_keep = True
                        break
                
                # 检查是否是当前正在处理的文件
                if file_path == current_audio_path:
                    should_keep = True
                
                # 检查是否是最近修改的文件（1小时内）
                try:
                    file_stat = os.stat(file_path)
                    file_age = datetime.now().timestamp() - file_stat.st_mtime
                    if file_age < 3600:  # 1小时内的文件保留
                        should_keep = True
                except:
                    pass
                
                if should_keep:
                    files_to_keep.append(file_name)
                else:
                    files_to_delete.append(file_path)
            
            # 5. 删除不需要的文件
            deleted_count = 0
            deleted_size = 0
            
            for file_path in files_to_delete:
                try:
                    file_size = os.path.getsize(file_path)
                    os.remove(file_path)
                    deleted_count += 1
                    deleted_size += file_size
                    print(f"[{current_task_id}] 已删除临时文件: {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"[{current_task_id}] 删除文件失败 {file_path}: {e}")
            
            # 6. 记录清理结果
            if deleted_count > 0:
                size_mb = deleted_size / (1024 * 1024)
                print(f"[{current_task_id}] 临时文件清理完成：删除 {deleted_count} 个文件，释放 {size_mb:.2f}MB 空间")
                print(f"[{current_task_id}] 保留文件数量: {len(files_to_keep)}")
            else:
                print(f"[{current_task_id}] 无需清理临时文件")
                
        except Exception as e:
            print(f"[{current_task_id}] 临时文件清理失败: {e}")
    
    def _is_file_related_to_task(self, file_name: str, task_id: str) -> bool:
        """判断文件是否与特定任务相关"""
        try:
            # 1. 检查文件名中是否包含任务ID
            if task_id in file_name:
                return True
            
            # 2. 检查是否是该任务的视频标题相关文件
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.video_info and task.video_info.title:
                    # 清理文件名中的特殊字符进行比较
                    clean_title = re.sub(r'[^\w\s-]', '', task.video_info.title).strip()
                    clean_filename = re.sub(r'[^\w\s-]', '', file_name).strip()
                    
                    # 检查标题是否在文件名中
                    if clean_title and clean_title in clean_filename:
                        return True
                    
                    # 检查文件名是否在标题中
                    if clean_filename and clean_filename in clean_title:
                        return True
            
            # 3. 检查是否是分段音频文件（包含 segment 关键字）
            if 'segment' in file_name.lower():
                # 尝试从分段文件名中提取原始文件名
                base_name = file_name
                if '_segment_' in file_name:
                    base_name = file_name.split('_segment_')[0]
                elif 'segment' in file_name:
                    base_name = re.sub(r'_?segment_?\d+', '', file_name)
                
                # 递归检查基础文件名是否与任务相关
                return self._is_file_related_to_task(base_name, task_id)
            
            return False
            
        except Exception as e:
            print(f"检查文件关联性失败 {file_name} <-> {task_id}: {e}")
            return False
    
    def _format_timestamp(self, seconds: float) -> str:
        """格式化时间戳为可读格式"""
        if not seconds or seconds <= 0:
            return "00:00"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"