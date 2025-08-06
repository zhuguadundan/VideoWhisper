from flask import Blueprint, render_template, request, jsonify, send_file
import threading
import os
from app.services.video_processor import VideoProcessor
from app.services.speech_to_text import SpeechToText
from app.services.text_processor import TextProcessor

main_bp = Blueprint('main', __name__)
video_processor = VideoProcessor()

@main_bp.route('/')
def index():
    """主页"""
    return render_template('index.html')

@main_bp.route('/settings')
def settings():
    """设置页面"""
    return render_template('settings.html')

@main_bp.route('/api/process', methods=['POST'])
def process_video():
    """处理视频请求"""
    try:
        data = request.get_json()
        video_url = data.get('video_url', '').strip()
        llm_provider = data.get('llm_provider', 'openai')
        
        if not video_url:
            return jsonify({'success': False, 'message': '请提供视频URL'})
        
        # 创建任务
        task_id = video_processor.create_task(video_url)
        
        # 在后台线程中处理视频
        thread = threading.Thread(
            target=video_processor.process_video,
            args=(task_id, llm_provider)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '任务已创建，开始处理...'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'创建任务失败: {str(e)}'
        })

@main_bp.route('/api/progress/<task_id>')
def get_progress(task_id):
    """获取处理进度"""
    try:
        progress = video_processor.get_task_progress(task_id)
        return jsonify({
            'success': True,
            'data': progress
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@main_bp.route('/api/result/<task_id>')
def get_result(task_id):
    """获取处理结果"""
    try:
        task = video_processor.get_task(task_id)
        if not task:
            return jsonify({
                'success': False,
                'message': '任务不存在'
            })
        
        if task.status != 'completed':
            return jsonify({
                'success': False,
                'message': f'任务未完成，当前状态: {task.status}'
            })
        
        return jsonify({
            'success': True,
            'data': {
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
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

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
            'transcript': 'transcript.txt',
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
        
        # 简化文件名格式
        def get_simple_filename(title: str, file_type: str, extension: str) -> str:
            # 提取标题关键词（取前6个字符）
            if title:
                # 移除特殊字符，只保留中文、英文、数字
                import re
                clean_title = re.sub(r'[^\u4e00-\u9fa5\w\s]', '', title)
                # 截取前6个字符
                short_title = clean_title[:6] if clean_title else "视频"
            else:
                short_title = "视频"
            
            # 根据文件类型生成简短名称
            if file_type == 'transcript':
                return f"{short_title}逐字稿.{extension}"
            elif file_type == 'summary':
                return f"{short_title}总结报告.{extension}"
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

@main_bp.route('/api/test-connection', methods=['POST'])
def test_api_connection():
    """测试API连接"""
    try:
        data = request.get_json()
        provider = data.get('provider')
        config = data.get('config', {})
        
        if provider == 'siliconflow':
            # 测试硅基流动API
            if not config.get('api_key'):
                return jsonify({'success': False, 'error': 'API Key未提供'})
            
            import requests
            headers = {'Authorization': f'Bearer {config["api_key"]}'}
            
            try:
                response = requests.get(
                    f"{config['base_url']}/models",
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    return jsonify({
                        'success': True,
                        'message': f'硅基流动API连接成功，模型: {config.get("model", "")}'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'API响应错误: {response.status_code}'
                    })
            except requests.RequestException as e:
                return jsonify({
                    'success': False,
                    'error': f'网络连接失败: {str(e)}'
                })
                
        elif provider == 'openai':
            try:
                import openai
                client = openai.OpenAI(
                    api_key=config.get('api_key'),
                    base_url=config.get('base_url') if config.get('base_url') else None
                )
                
                response = client.chat.completions.create(
                    model=config.get('model', 'gpt-4'),
                    messages=[{"role": "user", "content": "Hello"}],
                    max_tokens=5
                )
                
                return jsonify({
                    'success': True,
                    'message': f'OpenAI API连接成功，模型: {config.get("model", "gpt-4")}'
                })
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'OpenAI API测试失败: {str(e)}'
                })
                
        elif provider == 'gemini':
            try:
                import google.generativeai as genai
                genai.configure(api_key=config.get('api_key'))
                model = genai.GenerativeModel(config.get('model', 'gemini-pro'))
                
                response = model.generate_content("Hello")
                
                return jsonify({
                    'success': True,
                    'message': f'Gemini API连接成功，模型: {config.get("model", "gemini-pro")}'
                })
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'Gemini API测试失败: {str(e)}'
                })
                
        else:
            return jsonify({
                'success': False,
                'error': f'不支持的服务提供商: {provider}'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'测试过程中发生错误: {str(e)}'
        })