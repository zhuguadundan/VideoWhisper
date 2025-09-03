from flask import Blueprint, render_template, request, jsonify, send_file
import threading
import os
import shutil
import glob
from datetime import datetime
from app.services.video_processor import VideoProcessor
from app.services.video_downloader import VideoDownloader
from app.services.speech_to_text import SpeechToText
from app.services.text_processor import TextProcessor
from app.services.file_uploader import FileUploader
from app.models.data_models import UploadTask
from app.utils.error_handler import api_error_handler, safe_json_response
import logging

try:
    import openai
except ImportError:
    openai = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

main_bp = Blueprint('main', __name__)
video_processor = VideoProcessor()
video_downloader = VideoDownloader()
file_uploader = FileUploader()

@main_bp.route('/')
def index():
    """主页"""
    return render_template('index.html')

@main_bp.route('/settings')
def settings():
    """设置页面"""
    return render_template('settings.html')

@main_bp.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': 'v0.16.0',
        'features': [
            'audio_only_download',
            'automatic_temp_cleanup',
            'docker_optimized',
            'youtube_cookies_support'
        ]
    })

@main_bp.route('/api/providers', methods=['GET'])
@api_error_handler
def get_available_providers():
    """获取可用的AI服务提供商"""
    providers = video_processor.text_processor.get_available_providers()
    default_provider = video_processor.text_processor.get_default_provider() if providers else None
    
    return safe_json_response(
        success=True,
        data={
            'providers': providers,
            'default': default_provider
        }
    )

@main_bp.route('/api/video-info', methods=['POST'])
@api_error_handler
def get_video_info():
    """获取视频基本信息（仅用于显示）"""
    data = request.get_json()
    if not data:
        raise ValueError("请求数据不能为空")
        
    video_url = data.get('video_url', '').strip()
    if not video_url:
        raise ValueError("请提供视频URL")
        
    try:
        info = video_downloader.get_video_info(video_url)
        return safe_json_response(
            success=True,
            data=info,
            message='视频信息获取成功'
        )
    except Exception as e:
        logging.error(f"获取视频信息失败: {str(e)}")
        raise Exception(f"获取视频信息失败: {str(e)}")

@main_bp.route('/api/upload', methods=['POST'])
@api_error_handler
def upload_file():
    """文件上传端点"""
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            return safe_json_response(
                success=False,
                error="请选择要上传的文件"
            )
        
        file = request.files['file']
        if file.filename == '':
            return safe_json_response(
                success=False,
                error="请选择要上传的文件"
            )
        
        # 获取文件信息
        original_filename = file.filename
        file_size = 0
        file_content = b''
        
        # 计算文件大小和读取内容
        file.stream.seek(0, 2)  # 移动到文件末尾
        file_size = file.stream.tell()
        file.stream.seek(0)  # 回到文件开头
        
        # 获取MIME类型
        mime_type = file.mimetype or 'application/octet-stream'
        
        logging.info(f"文件上传请求: filename={original_filename}, size={file_size}, mime_type={mime_type}")
        
        # 验证文件
        try:
            file_info = file_uploader._get_file_info(original_filename, file_size)
            is_valid, message = file_uploader._validate_file(original_filename, file_size, mime_type)
            if not is_valid:
                return safe_json_response(
                    success=False,
                    error=message
                )
        except Exception as e:
            return safe_json_response(
                success=False,
                error=f"文件验证失败: {str(e)}"
            )
        
        # 创建上传任务
        try:
            task_id = video_processor.create_upload_task(
                original_filename=original_filename,
                file_size=file_size,
                file_type=file_info['file_type'],
                mime_type=mime_type
            )
        except Exception as e:
            return safe_json_response(
                success=False,
                error=f"创建上传任务失败: {str(e)}"
            )
        
        # 保存文件
        try:
            upload_result = file_uploader.save_uploaded_file(
                file_obj=file,
                original_filename=original_filename,
                file_size=file_size
            )
            
            if not upload_result['success']:
                # 标记任务为失败
                video_processor.fail_upload_task(task_id, upload_result['error'])
                return safe_json_response(
                    success=False,
                    error=upload_result['error']
                )
            
            # 完成上传任务
            video_processor.complete_upload_task(
                task_id=task_id,
                file_path=upload_result['file_path'],
                file_duration=upload_result.get('file_duration', 0)
            )
            
            return safe_json_response(
                success=True,
                data={
                    'task_id': task_id,
                    'file_info': {
                        'original_filename': original_filename,
                        'file_size': file_size,
                        'file_type': file_info['file_type'],
                        'mime_type': mime_type,
                        'need_audio_extraction': file_info['need_audio_extraction'],
                        'file_path': upload_result['file_path']
                    }
                },
                message='文件上传成功'
            )
            
        except Exception as e:
            # 标记任务为失败
            video_processor.fail_upload_task(task_id, str(e))
            return safe_json_response(
                success=False,
                error=f"文件上传失败: {str(e)}"
            )
    
    except Exception as e:
        logging.error(f"文件上传端点异常: {str(e)}")
        return safe_json_response(
            success=False,
            error=f"服务器错误: {str(e)}"
        )

@main_bp.route('/api/upload/<task_id>/progress', methods=['GET'])
@api_error_handler
def get_upload_progress(task_id):
    """获取上传进度"""
    try:
        task = video_processor.get_task(task_id)
        if not task:
            return safe_json_response(
                success=False,
                error="任务不存在"
            )
        
        if not isinstance(task, UploadTask):
            return safe_json_response(
                success=False,
                error="不是上传任务"
            )
        
        return safe_json_response(
            success=True,
            data={
                'task_id': task_id,
                'upload_progress': task.upload_progress,
                'upload_status': task.upload_status,
                'upload_error_message': task.upload_error_message,
                'file_size': task.file_size,
                'file_type': task.file_type,
                'original_filename': task.original_filename
            }
        )
    
    except Exception as e:
        logging.error(f"获取上传进度异常: {str(e)}")
        return safe_json_response(
            success=False,
            error=f"服务器错误: {str(e)}"
        )

@main_bp.route('/api/process-upload', methods=['POST'])
@api_error_handler
def process_upload():
    """处理上传的文件"""
    data = request.get_json()
    if not data:
        raise ValueError("请求数据不能为空")
    
    task_id = data.get('task_id', '').strip()
    if not task_id:
        raise ValueError("请提供任务ID")
    
    llm_provider = data.get('llm_provider', 'openai')
    api_config = data.get('api_config', {})
    
    logging.info(f"process_upload请求: task_id={task_id}, llm_provider={llm_provider}")
    
    # 获取任务
    task = video_processor.get_task(task_id)
    if not task:
        logging.error(f"任务不存在: {task_id}")
        raise ValueError("任务不存在")
    
    logging.info(f"获取到任务: id={task.id}, type={type(task)}, upload_status={task.upload_status}")
    
    if not isinstance(task, UploadTask):
        logging.error(f"不是上传任务: task_id={task_id}, task_type={type(task)}")
        raise ValueError("不是上传任务")
    
    try:
        upload_status = task.upload_status
        logging.info(f"任务上传状态: {upload_status}")
    except AttributeError as e:
        logging.error(f"UploadTask缺少upload_status属性: task_id={task_id}, error={e}")
        logging.error(f"UploadTask对象内容: {vars(task)}")
        raise ValueError(f"任务状态不完整，upload_status属性缺失: {e}")
    
    if upload_status != 'completed':
        logging.error(f"文件上传未完成: task_id={task_id}, upload_status={upload_status}")
        raise ValueError("文件上传未完成，请等待上传完成后再处理")
    
    logging.info(f"开始处理上传文件任务: {task_id}, 文件: {task.original_filename}, audio_file_path={task.audio_file_path}")
    
    # 创建处理函数
    def safe_process_upload():
        try:
            logging.info(f"启动处理上传文件线程: {task_id}")
            video_processor.process_upload(task_id, llm_provider, api_config)
            logging.info(f"上传文件任务 {task_id} 处理完成")
        except Exception as e:
            logging.exception(f"上传文件处理线程异常 [{task_id}]: {e}")
            # 确保任务状态被正确更新
            task = video_processor.get_task(task_id)
            if task:
                task.status = "failed"
                task.error_message = f"处理异常: {str(e)}"
                video_processor.save_tasks_to_disk()
    
    # 在后台线程中处理文件
    thread = threading.Thread(target=safe_process_upload)
    thread.daemon = True
    thread.start()
    logging.info(f"已启动处理线程: {task_id}")
    
    return safe_json_response(
        success=True,
        data={'task_id': task_id},
        message='任务已创建，开始处理...'
    )

@main_bp.route('/api/upload/config', methods=['GET'])
@api_error_handler
def get_upload_config():
    """获取上传配置信息"""
    try:
        config = file_uploader.get_upload_config()
        return safe_json_response(
            success=True,
            data=config,
            message='获取上传配置成功'
        )
    except Exception as e:
        logging.error(f"获取上传配置异常: {str(e)}")
        return safe_json_response(
            success=False,
            error=f"获取上传配置失败: {str(e)}"
        )

@main_bp.route('/api/process', methods=['POST'])
@api_error_handler
def process_video():
    """处理视频请求 - 简化版，仅音频下载"""
    data = request.get_json()
    if not data:
        raise ValueError("请求数据不能为空")
        
    video_url = data.get('video_url', '').strip()
    if not video_url:
        raise ValueError("请提供视频URL")
        
    llm_provider = data.get('llm_provider', 'openai')
    api_config = data.get('api_config', {})
    youtube_cookies = data.get('youtube_cookies', '')  # 获取 YouTube cookies
    
    # 创建任务（支持 cookies 参数）
    task_id = video_processor.create_task(video_url, youtube_cookies)
    logging.info(f"创建新任务: {task_id}, URL: {video_url} (仅音频模式)")
    if youtube_cookies:
        logging.info(f"任务 {task_id} 使用了 YouTube cookies")
    
    # 创建带异常处理的处理函数
    def safe_process_video():
        try:
            video_processor.process_video(task_id, llm_provider, api_config)
            logging.info(f"任务 {task_id} 处理完成")
        except Exception as e:
            # 确保任务状态被正确更新
            task = video_processor.get_task(task_id)
            if task:
                task.status = "failed"
                task.error_message = f"处理异常: {str(e)}"
                video_processor.save_tasks_to_disk()
            logging.exception(f"视频处理线程异常 [{task_id}]: {e}")
    
    # 在后台线程中处理视频
    thread = threading.Thread(target=safe_process_video)
    thread.daemon = True
    thread.start()
    
    return safe_json_response(
        success=True,
        data={'task_id': task_id},
        message='任务已创建，开始处理...'
    )

@main_bp.route('/api/progress/<task_id>')
@api_error_handler
def get_progress(task_id):
    """获取处理进度"""
    progress = video_processor.get_task_progress(task_id)
    if 'error' in progress:
        return safe_json_response(success=False, error=progress['error'])
    
    return safe_json_response(success=True, data=progress)

@main_bp.route('/api/result/<task_id>')
@api_error_handler
def get_result(task_id):
    """获取处理结果"""
    task = video_processor.get_task(task_id)
    if not task:
        raise ValueError("任务不存在")
    
    if task.status != 'completed':
        raise ValueError(f"任务未完成，当前状态: {task.status}")
    
    result_data = {
        'video_info': {
            'title': task.video_info.title if task.video_info else '',
            'uploader': task.video_info.uploader if task.video_info else '',
            'duration': task.video_info.duration if task.video_info else 0,
            'url': task.video_url
        },
        'transcript': task.transcript,
        'summary': task.summary,
        'analysis': task.analysis
    }
    
    return safe_json_response(success=True, data=result_data)

@main_bp.route('/api/download/<task_id>/<file_type>')
def download_file(task_id, file_type):
    """下载结果文件"""
    try:
        task = video_processor.get_task(task_id)
        if not task or task.status != 'completed':
            return jsonify({
                'success': False,
                'message': '任务不存在或未完成'
            })
        
        output_dir = video_processor.output_dir
        task_dir = os.path.join(output_dir, task_id)
        
        # 动态查找实际的文件名
        if file_type == 'transcript':
            # 查找以transcript_开头的.md文件
            transcript_files = glob.glob(os.path.join(task_dir, 'transcript_*.md'))
            if not transcript_files:
                # 如果没找到，尝试查找transcript.md
                transcript_files = glob.glob(os.path.join(task_dir, 'transcript.md'))
            if not transcript_files:
                # 如果还没找到，尝试查找transcript.txt
                transcript_files = glob.glob(os.path.join(task_dir, 'transcript.txt'))
            if transcript_files:
                file_path = transcript_files[0]
            else:
                return jsonify({
                    'success': False,
                    'message': '逐字稿文件不存在'
                })
        elif file_type == 'summary':
            # 查找以summary_开头的.md文件
            summary_files = glob.glob(os.path.join(task_dir, 'summary_*.md'))
            if not summary_files:
                # 如果没找到，尝试查找summary.md
                summary_files = glob.glob(os.path.join(task_dir, 'summary.md'))
            if summary_files:
                file_path = summary_files[0]
            else:
                return jsonify({
                    'success': False,
                    'message': '总结报告文件不存在'
                })
        elif file_type == 'data':
            # 查找以data_开头的.json文件
            data_files = glob.glob(os.path.join(task_dir, 'data_*.json'))
            if not data_files:
                # 如果没找到，尝试查找data.json
                data_files = glob.glob(os.path.join(task_dir, 'data.json'))
            if data_files:
                file_path = data_files[0]
            else:
                return jsonify({
                    'success': False,
                    'message': '数据文件不存在'
                })
        else:
            return jsonify({
                'success': False,
                'message': '不支持的文件类型'
            })
        
        # 简化文件名格式
        def get_simple_filename(title: str, file_type: str, extension: str) -> str:
            import re
            
            # 简化标题处理，避免过度复杂化
            if title:
                # 移除文件扩展名（如果标题包含）
                clean_title = re.sub(r'\.(mp4|avi|mov|mkv|webm|flv|mp3|wav|aac|m4a|ogg)$', '', title, flags=re.IGNORECASE)
                # 移除特殊字符，保留中文、英文、数字
                clean_title = re.sub(r'[^\u4e00-\u9fa5\w\s]', '', clean_title)
                clean_title = clean_title.strip()
                
                # 限制长度
                if len(clean_title) > 20:
                    clean_title = clean_title[:20]
                
                short_title = clean_title if clean_title else "视频"
            else:
                short_title = "视频"
            
            # 根据文件类型生成简短名称
            if file_type == 'transcript':
                return f"{short_title}_逐字稿.{extension}"
            elif file_type == 'summary':
                return f"{short_title}_总结报告.{extension}"
            elif file_type == 'data':
                return f"{short_title}_完整数据.{extension}"
            else:
                return f"{short_title}_{file_type}.{extension}"
        
        extension = os.path.splitext(file_path)[1][1:]  # 获取实际文件的扩展名，去掉点号
        download_filename = get_simple_filename(
            task.video_info.title if task.video_info else '', 
            file_type, 
            extension
        )
        
        # 根据文件扩展名设置正确的MIME类型
        if extension.lower() == 'md':
            mimetype = 'text/markdown; charset=utf-8'
        elif extension.lower() == 'json':
            mimetype = 'application/json; charset=utf-8'
        else:
            mimetype = 'text/plain; charset=utf-8'
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype=mimetype
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@main_bp.route('/api/tasks')
def list_tasks():
    """获取所有任务列表"""
    try:
        tasks_data = []
        for task_id, task in video_processor.tasks.items():
            tasks_data.append({
                'id': task.id,
                'video_url': task.video_url,
                'status': task.status,
                'progress': task.progress,
                'title': task.video_info.title if task.video_info else '',
                'created_at': task.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'error_message': task.error_message
            })
        
        # 按创建时间倒序排列
        tasks_data.sort(key=lambda x: x['created_at'], reverse=True)
        
        return jsonify({
            'success': True,
            'data': tasks_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@main_bp.route('/files')
def files_management():
    """文件管理页面"""
    return render_template('files.html')

@main_bp.route('/api/files')
def list_files():
    """获取所有文件列表"""
    try:
        files_data = []
        
        # 扫描输出目录
        output_dir = video_processor.output_dir
        temp_dir = video_processor.temp_dir
        
        if os.path.exists(output_dir):
            for task_id in os.listdir(output_dir):
                task_path = os.path.join(output_dir, task_id)
                if os.path.isdir(task_path):
                    # 获取任务信息
                    task = video_processor.get_task(task_id)
                    task_title = task.video_info.title if task and task.video_info else task_id[:8]
                    
                    # 扫描任务目录下的所有文件
                    for file_name in os.listdir(task_path):
                        file_path = os.path.join(task_path, file_name)
                        if os.path.isfile(file_path):
                            file_stats = os.stat(file_path)
                            file_size = file_stats.st_size
                            modified_time = datetime.fromtimestamp(file_stats.st_mtime)
                            
                            # 确定文件类型和描述
                            file_type, description, download_type = get_file_info(file_name)
                            
                            files_data.append({
                                'id': f"{task_id}/{file_name}",
                                'task_id': task_id,
                                'file_name': file_name,
                                'file_type': file_type,
                                'description': description,
                                'download_type': download_type,
                                'task_title': task_title,
                                'size': file_size,
                                'size_human': format_file_size(file_size),
                                'modified_time': modified_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'file_path': file_path
                            })
        
        # 扫描临时目录的视频和音频文件
        if os.path.exists(temp_dir):
            for file_name in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file_name)
                if os.path.isfile(file_path):
                    file_stats = os.stat(file_path)
                    file_size = file_stats.st_size
                    modified_time = datetime.fromtimestamp(file_stats.st_mtime)
                    
                    file_type, description, download_type = get_file_info(file_name)
                    
                    files_data.append({
                        'id': f"temp/{file_name}",
                        'task_id': 'temp',
                        'file_name': file_name,
                        'file_type': file_type,
                        'description': description,
                        'download_type': download_type,
                        'task_title': '临时文件',
                        'size': file_size,
                        'size_human': format_file_size(file_size),
                        'modified_time': modified_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'file_path': file_path
                    })
        
        # 按修改时间倒序排列
        files_data.sort(key=lambda x: x['modified_time'], reverse=True)
        
        return jsonify({
            'success': True,
            'data': files_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@main_bp.route('/api/files/download/<path:file_id>')
def download_managed_file(file_id):
    """下载指定文件"""
    try:
        # 解析文件ID
        if '/' not in file_id:
            return jsonify({'success': False, 'message': '无效的文件ID'})
            
        parts = file_id.split('/')
        if len(parts) < 2:
            return jsonify({'success': False, 'message': '无效的文件ID格式'})
        
        task_id = parts[0]
        file_name = '/'.join(parts[1:])
        
        # 构造文件路径
        if task_id == 'temp':
            file_path = os.path.join(video_processor.temp_dir, file_name)
        else:
            file_path = os.path.join(video_processor.output_dir, task_id, file_name)
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': '文件不存在'})
        
        return send_file(file_path, as_attachment=True, download_name=file_name)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/files/delete', methods=['POST'])
def delete_files():
    """删除指定文件"""
    try:
        data = request.get_json()
        logging.info(f"Delete request received with data: {data}")
        file_ids = data.get('file_ids', [])
        
        if not file_ids:
            logging.warning("No file_ids provided in delete request")
            return jsonify({'success': False, 'message': '未指定要删除的文件'})
        
        deleted_count = 0
        errors = []
        
        for file_id in file_ids:
            try:
                logging.info(f"Processing delete for file_id: {file_id}")
                # 解析文件ID
                if '/' not in file_id:
                    errors.append(f'{file_id}: 无效的文件ID')
                    continue
                    
                parts = file_id.split('/')
                if len(parts) < 2:
                    errors.append(f'{file_id}: 无效的文件ID格式')
                    continue
                
                task_id = parts[0]
                file_name = '/'.join(parts[1:])
                
                # 构造文件路径
                if task_id == 'temp':
                    file_path = os.path.join(video_processor.temp_dir, file_name)
                else:
                    file_path = os.path.join(video_processor.output_dir, task_id, file_name)
                
                logging.info(f"Attempting to delete file: {file_path}")
                
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
                    logging.info(f"Successfully deleted: {file_path}")
                else:
                    errors.append(f'{file_name}: 文件不存在')
                    logging.warning(f"File not found: {file_path}")
                    
            except Exception as e:
                errors.append(f'{file_id}: {str(e)}')
                logging.error(f"Error deleting file {file_id}: {str(e)}")
        
        result = {
            'success': True,
            'message': f'成功删除 {deleted_count} 个文件',
            'deleted_count': deleted_count,
            'errors': errors
        }
        
        logging.info(f"Delete operation completed: {result}")
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Delete operation failed: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        })

@main_bp.route('/api/files/delete-task/<task_id>', methods=['POST'])
def delete_task_files(task_id):
    """删除整个任务的所有文件"""
    try:
        if task_id == 'temp':
            # 清空临时目录
            temp_dir = video_processor.temp_dir
            if os.path.exists(temp_dir):
                for file_name in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file_name)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                return jsonify({
                    'success': True,
                    'message': '临时文件已清空'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '临时目录不存在'
                })
        else:
            # 删除指定任务目录
            task_dir = os.path.join(video_processor.output_dir, task_id)
            if os.path.exists(task_dir):
                shutil.rmtree(task_dir)
                
                # 从内存中移除任务
                if task_id in video_processor.tasks:
                    del video_processor.tasks[task_id]
                
                return jsonify({
                    'success': True,
                    'message': f'任务 {task_id} 的所有文件已删除'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '任务目录不存在'
                })
                
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

def get_file_info(file_name):
    """获取文件类型信息"""
    file_name_lower = file_name.lower()
    
    if file_name_lower.endswith('.txt'):
        if 'transcript' in file_name_lower:
            if 'timestamp' in file_name_lower:
                return 'transcript', '带时间戳的逐字稿', 'transcript'
            else:
                return 'transcript', '逐字稿', 'transcript'
        else:
            return 'text', '文本文件', 'text'
    elif file_name_lower.endswith('.md'):
        return 'summary', '总结报告', 'summary'
    elif file_name_lower.endswith('.json'):
        return 'data', '数据文件', 'data'
    elif file_name_lower.endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv')):
        return 'video', '视频文件', 'video'
    elif file_name_lower.endswith(('.mp3', '.wav', '.aac', '.m4a', '.ogg')):
        return 'audio', '音频文件', 'audio'
    elif file_name_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
        return 'image', '图片文件', 'image'
    else:
        return 'other', '其他文件', 'other'

def format_file_size(size_bytes):
    """格式化文件大小"""
    if size_bytes == 0:
        return "0B"
    
    import math
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"

@main_bp.route('/api/test-connection', methods=['POST'])
@api_error_handler
def test_api_connection():
    """测试API连接"""
    data = request.get_json()
    if not data:
        raise ValueError("请求数据不能为空")
        
    provider = data.get('provider')
    config = data.get('config', {})
    
    logging.info(f"测试API连接 - 提供商: {provider}, 配置keys: {list(config.keys()) if config else 'None'}")
    
    if not provider:
        raise ValueError("未指定服务提供商")
    
    if provider == 'siliconflow':
        return test_siliconflow_connection(config)
    elif provider == 'text_processor':
        return test_text_processor_connection(config)
    elif provider == 'openai':
        return test_openai_connection(config)
    elif provider == 'gemini':
        return test_gemini_connection(config)
    else:
        raise ValueError(f'不支持的服务提供商: {provider}')

def test_siliconflow_connection(config):
    """测试硅基流动API连接"""
    if not config.get('api_key'):
        raise ValueError('API Key未提供')
    
    import requests
    headers = {'Authorization': f'Bearer {config["api_key"]}'}
    
    response = requests.get(
        f"{config['base_url']}/models",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        return safe_json_response(
            success=True,
            message=f'硅基流动API连接成功，模型: {config.get("model", "")}'
        )
    else:
        raise ConnectionError(f'API响应错误: {response.status_code}')

def test_text_processor_connection(config):
    """测试文本处理器连接"""
    actual_provider = config.get('actual_provider')
    logging.info(f"测试文本处理器连接 - actual_provider: {actual_provider}")
    
    if actual_provider == 'siliconflow':
        return test_siliconflow_text_processor(config)
    elif actual_provider == 'custom':
        return test_openai_connection(config, is_text_processor=True)
    elif actual_provider == 'openai':
        return test_openai_connection(config, is_text_processor=True)
    elif actual_provider == 'gemini':
        return test_gemini_connection(config, is_text_processor=True)
    else:
        raise ValueError(f'不支持的文本处理提供商: {actual_provider}')

def test_siliconflow_text_processor(config):
    """测试硅基流动作为文本处理器"""
    if not config.get('api_key'):
        raise ValueError('API Key未提供')
    
    import requests
    headers = {'Authorization': f'Bearer {config["api_key"]}'}
    base_url = config.get('base_url') or 'https://api.siliconflow.cn/v1'
    
    response = requests.get(
        f"{base_url}/models",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        return safe_json_response(
            success=True,
            message=f'硅基流动文本处理API连接成功，模型: {config.get("model", "Qwen/Qwen3-Coder-30B-A3B-Instruct")}'
        )
    else:
        raise ConnectionError(f'API响应错误: {response.status_code}')

def test_openai_connection(config, is_text_processor=False):
    """测试OpenAI连接（包括自定义兼容OpenAI的API），使用模型列表，不消耗token"""
    if not openai:
        raise ImportError('OpenAI库未安装，请先安装: pip install openai')
    
    if not config.get('api_key'):
        raise ValueError('API Key未提供')
    
    # 对于自定义提供商，Base URL是必需的
    if is_text_processor and config.get('actual_provider') == 'custom':
        if not config.get('base_url'):
            raise ValueError('自定义提供商需要提供Base URL')
    
    try:
        client = openai.OpenAI(
            api_key=config.get('api_key'),
            base_url=config.get('base_url') if config.get('base_url') else None
        )
        
        # 使用模型列表进行测试
        models = client.models.list()
        if not list(models):
            raise ConnectionError("模型列表为空，请检查API密钥或Base URL")
        
        # 根据是否为自定义提供商显示不同的成功消息
        if is_text_processor and config.get('actual_provider') == 'custom':
            service_type = "自定义文本处理"
            model_info = config.get('model', '未知')
        else:
            service_type = "文本处理" if is_text_processor else ""
            model_info = config.get('model', '未知')
            
        return safe_json_response(
            success=True,
            message=f'OpenAI {service_type}API连接成功，模型: {model_info} (通过模型列表测试)'
        )
        
    except Exception as e:
        # 提供更详细的错误信息
        error_msg = str(e)
        if 'unauthorized' in error_msg.lower() or '401' in error_msg:
            error_msg = 'API密钥无效或权限不足'
        elif 'not found' in error_msg.lower() or '404' in error_msg:
            error_msg = 'API端点不存在，请检查Base URL是否正确'
        elif 'connection' in error_msg.lower():
            error_msg = '网络连接失败，请检查Base URL是否可访问'
        
        raise ConnectionError(f'连接测试失败: {error_msg}')

def test_gemini_connection(config, is_text_processor=False):
    """测试Gemini连接"""
    if not genai:
        raise ImportError('Gemini库未安装，请先安装: pip install google-generativeai')
    
    if not config.get('api_key'):
        raise ValueError('API Key未提供')
    
    genai.configure(api_key=config.get('api_key'))
    
    if config.get('base_url'):
        # 如果有自定义base_url，需要设置（Gemini可能需要特殊处理）
        pass
    
    model = genai.GenerativeModel(config.get('model', 'gemini-pro'))
    response = model.generate_content("Hello")
    
    service_type = "文本处理" if is_text_processor else ""
    return safe_json_response(
        success=True,
        message=f'Gemini {service_type}API连接成功，模型: {config.get("model", "gemini-pro")}'
    )

@main_bp.route('/api/stop-all-tasks', methods=['POST'])
@api_error_handler
def stop_all_tasks():
    """停止所有正在处理的任务"""
    try:
        # 获取所有正在处理的任务
        processing_tasks = []
        for task_id, task in video_processor.tasks.items():
            if task.status == "processing":
                processing_tasks.append(task_id)
        
        if not processing_tasks:
            return safe_json_response(
                success=True,
                message="当前没有正在处理的任务",
                data={'stopped_tasks': []}
            )
        
        # 停止所有正在处理的任务
        stopped_count = 0
        for task_id in processing_tasks:
            task = video_processor.get_task(task_id)
            if task and task.status == "processing":
                task.status = "failed"
                task.error_message = "用户手动停止任务"
                task.progress = 0
                task.progress_stage = "已停止"
                task.progress_detail = "任务已被用户手动停止"
                stopped_count += 1
                logging.info(f"手动停止任务: {task_id}")
        
        # 保存任务状态
        video_processor.save_tasks_to_disk()
        
        return safe_json_response(
            success=True,
            message=f"成功停止 {stopped_count} 个任务",
            data={
                'stopped_tasks': processing_tasks,
                'stopped_count': stopped_count
            }
        )
        
    except Exception as e:
        logging.error(f"停止所有任务失败: {e}")
        raise Exception(f"停止任务失败: {str(e)}")