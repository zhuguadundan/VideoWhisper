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
        
        file_mapping = {
            'transcript': 'transcript.md',
            'summary': 'summary.md',
            'data': 'data.json'
        }
        
        if file_type not in file_mapping:
            return jsonify({
                'success': False,
                'message': '不支持的文件类型'
            })
        
        file_path = os.path.join(task_dir, file_mapping[file_type])
        
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': '文件不存在'
            })
        
        # 智能简化文件名格式
        def get_simple_filename(title: str, file_type: str, extension: str) -> str:
            import re
            
            if title:
                # 移除常见的无用词汇
                noise_words = ['视频', '直播', '录播', '完整版', '高清', 'HD', '4K', '1080P', '合集', '精选', '最新', '官方']
                clean_title = title
                
                # 移除噪音词汇
                for noise in noise_words:
                    clean_title = clean_title.replace(noise, '')
                
                # 移除特殊字符，只保留中文、英文、数字和常用标点
                clean_title = re.sub(r'[^\u4e00-\u9fa5\w\s\-\|\(\)\[\]【】（）]', '', clean_title)
                clean_title = clean_title.strip()
                
                # 如果标题太长，智能截取
                if len(clean_title) > 15:
                    # 尝试从标题中找到关键词
                    # 按分隔符分割，取最重要的部分
                    parts = re.split(r'[\-\|\(\)\[\]【】（）]', clean_title)
                    if parts and len(parts) > 1:
                        # 过滤空字符串并按长度排序
                        valid_parts = [p.strip() for p in parts if p.strip()]
                        if valid_parts:
                            # 取最长且最有意义的部分
                            main_part = max(valid_parts, key=len)
                            if len(main_part) > 10:
                                clean_title = main_part[:10]
                            else:
                                clean_title = main_part
                        else:
                            clean_title = clean_title[:10]
                    else:
                        # 直接截取前10个字符
                        clean_title = clean_title[:10]
                
                # 去除首尾空格和常见分隔符
                clean_title = clean_title.strip('- |()[]【】（）')
                short_title = clean_title if clean_title else "视频"
            else:
                short_title = "视频"
            
            # 根据文件类型生成简短名称
            if file_type == 'transcript':
                return f"{short_title}_逐字稿.md"
            elif file_type == 'summary':
                return f"{short_title}_总结报告.md"
            elif file_type == 'data':
                return f"{short_title}_完整数据.{extension}"
            else:
                return f"{short_title}_{file_type}.{extension}"
        
        extension = file_mapping[file_type].split('.')[-1]
        download_filename = get_simple_filename(
            task.video_info.title if task.video_info else '', 
            file_type, 
            extension
        )
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=download_filename
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