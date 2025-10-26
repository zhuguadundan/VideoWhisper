from flask import Flask, jsonify, request
from app.config.settings import Config
from app.utils.certificate_manager import CertificateManager, create_ssl_context
import logging
from logging.handlers import RotatingFileHandler
import traceback
import os

def create_app():
    app = Flask(__name__, 
                template_folder='../web/templates',
                static_folder='../web/static')
    
    app.config.from_object(Config)
    
    # 获取HTTPS配置
    https_config = Config.get_https_config()
    
    # 初始化证书管理器
    cert_manager = CertificateManager(https_config)
    
    # 自动生成证书（如果启用且不存在）
    if https_config['enabled'] and https_config['auto_generate']:
        print("HTTPS已启用，检查SSL证书...")
        if cert_manager.ensure_certificates():
            print("SSL证书已准备就绪")
        else:
            print("SSL证书生成失败，将仅使用HTTP")
    
    # 配置HTTPS上下文（如果证书存在）
    ssl_context = None
    if https_config['enabled'] and cert_manager.certificates_exist():
        try:
            ssl_context = create_ssl_context(https_config['cert_file'], https_config['key_file'])
            if ssl_context:
                print(f"HTTPS已启用，监听 {https_config['host']}:{https_config['port']}")
                # 将SSL上下文存储到app对象中，供run.py使用
                app.ssl_context = ssl_context
                app.https_config = https_config
            else:
                print("SSL上下文创建失败，将仅使用HTTP")
        except Exception as e:
            print(f"SSL上下文创建失败: {e}")
            https_config['enabled'] = False
    else:
        app.ssl_context = None
        app.https_config = https_config
    
    # 配置日志目录
    os.makedirs('logs', exist_ok=True)

    # 配置日志（滚动文件 + 控制台）
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # 滚动文件
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    file_handler.setFormatter(fmt)
    # 控制台
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    # 重置并添加
    root_logger.handlers = [file_handler, stream_handler]
    
    def is_api_request():
        """判断是否是API请求"""
        return request.path.startswith('/api/')
    
    # 覆盖默认错误处理，修正中文提示乱码（保留单套处理器，避免重复定义）
    @app.errorhandler(500)
    def _handle_internal_error_clean(e):
        logging.error(f"Internal Server Error: {str(e)}")
        logging.error(traceback.format_exc())
        if is_api_request():
            return jsonify({
                'success': False,
                'error': '服务器内部错误',
                'message': '系统出现内部错误，请稍后重试。如果问题持续存在，请联系管理员。'
            }), 500
        return f"<h1>服务器错误</h1><p>系统出现内部错误，请稍后重试</p>", 500

    @app.errorhandler(404)
    def _handle_not_found_clean(e):
        if is_api_request():
            return jsonify({
                'success': False,
                'error': '资源不存在',
                'message': '请求的API端点不存在'
            }), 404
        return f"<h1>页面未找到</h1><p>请求的页面不存在</p>", 404

    @app.errorhandler(405)
    def _handle_method_not_allowed_clean(e):
        if is_api_request():
            return jsonify({
                'success': False,
                'error': '请求方法不允许',
                'message': '请求方法不被允许，请检查HTTP方法'
            }), 405
        return f"<h1>请求方法不允许</h1><p>请求方法不被允许</p>", 405

    @app.errorhandler(400)
    def _handle_bad_request_clean(e):
        if is_api_request():
            return jsonify({
                'success': False,
                'error': '请求格式错误',
                'message': '请求数据格式不正确，请检查请求参数'
            }), 400
        return f"<h1>请求格式错误</h1><p>请求数据格式不正确</p>", 400

    @app.errorhandler(Exception)
    def handle_exception(e):
        # 记录详细的异常信息
        logging.exception(f"Unhandled exception: {str(e)}")
        logging.error(f"Request URL: {request.url}")
        logging.error(f"Request Method: {request.method}")
        try:
            if request.is_json:
                payload = request.get_json(silent=True) or {}
                if isinstance(payload, dict):
                    masked = {}
                    for k, v in payload.items():
                        if any(s in k.lower() for s in ['api_key', 'apikey', 'authorization', 'token', 'secret']):
                            masked[k] = '***'
                        else:
                            masked[k] = v
                    logging.error(f"Request JSON (masked): {masked}")
            else:
                body = request.get_data(cache=False) or b''
                logging.error(f"Request Body length: {len(body)}")
        except Exception:
            pass
        logging.error(traceback.format_exc())
        
        # 处理不同类型的异常，提供更友好的错误信息
        error_message = str(e)
        if 'Connection' in str(type(e).__name__):
            error_message = 'API连接失败，请检查网络连接或API配置'
        elif 'timeout' in str(e).lower():
            error_message = '请求超时，请稍后重试'
        elif 'api_key' in str(e).lower() or 'unauthorized' in str(e).lower():
            error_message = 'API密钥无效，请检查配置'
        elif 'file' in str(e).lower() and 'not found' in str(e).lower():
            error_message = '所需文件不存在，请检查文件路径'
        
        if is_api_request():
            return jsonify({
                'success': False,
                'error': '系统异常',
                'message': error_message if len(error_message) <= 200 else f'{error_message[:200]}...',
                'error_type': type(e).__name__
            }), 500
        else:
            return f"<h1>系统异常</h1><p>{error_message}</p>", 500
    
    # 注册蓝图
    from app.main import main_bp
    app.register_blueprint(main_bp)
    
    return app
