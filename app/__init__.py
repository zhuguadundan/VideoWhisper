from flask import Flask, jsonify, request
from app.config.settings import Config
from app.utils.certificate_manager import CertificateManager, create_ssl_context
import logging
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
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    def is_api_request():
        """判断是否是API请求"""
        return request.path.startswith('/api/')
    
    # 配置全局错误处理器
    @app.errorhandler(500)
    def handle_internal_error(e):
        logging.error(f"Internal Server Error: {str(e)}")
        logging.error(traceback.format_exc())
        
        if is_api_request():
            return jsonify({
                'success': False,
                'error': '服务器内部错误',
                'message': '系统出现内部错误，请稍后重试。如果问题持续存在，请联系管理员。'
            }), 500
        else:
            return f"<h1>服务器错误</h1><p>系统出现内部错误，请稍后重试</p>", 500
    
    @app.errorhandler(404)
    def handle_not_found(e):
        if is_api_request():
            return jsonify({
                'success': False,
                'error': '资源不存在',
                'message': '请求的API端点不存在'
            }), 404
        else:
            return f"<h1>页面未找到</h1><p>请求的页面不存在</p>", 404
    
    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        if is_api_request():
            return jsonify({
                'success': False,
                'error': '请求方法不允许',
                'message': '请求方法不被允许，请检查HTTP方法'
            }), 405
        else:
            return f"<h1>请求方法不允许</h1><p>请求方法不被允许</p>", 405
    
    @app.errorhandler(400)
    def handle_bad_request(e):
        if is_api_request():
            return jsonify({
                'success': False,
                'error': '请求格式错误',
                'message': '请求数据格式不正确，请检查请求参数'
            }), 400
        else:
            return f"<h1>请求格式错误</h1><p>请求数据格式不正确</p>", 400
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        # 记录详细的异常信息
        logging.exception(f"Unhandled exception: {str(e)}")
        logging.error(f"Request URL: {request.url}")
        logging.error(f"Request Method: {request.method}")
        logging.error(f"Request Data: {request.get_data(as_text=True)}")
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