from app import create_app
from app.config.settings import Config
import threading
import time
import os
import logging

def run_http_server(app, host, port):
    """启动HTTP服务器"""
    logging.info(f"启动HTTP服务器: http://{host}:{port}")
    # 启用多线程，避免长任务阻塞静态资源与API的快速响应
    app.run(host=host, port=port, debug=False, threaded=True)

def run_https_server(app, https_config, ssl_context):
    """启动HTTPS服务器"""
    try:
        logging.info(f"启动HTTPS服务器: https://{https_config['host']}:{https_config['port']}")
        app.run(
            host=https_config['host'],
            port=https_config['port'],
            ssl_context=ssl_context,
            debug=False,  # 生产环境不使用debug
            threaded=True  # 启用多线程支持
        )
    except Exception as e:
        logging.error(f"HTTPS服务器启动失败: {e}")

if __name__ == '__main__':
    app = create_app()
    
    # 读取配置文件获取web设置
    config = Config.load_config()
    web_config = config.get('web', {})
    http_host = web_config.get('host', '0.0.0.0')
    http_port = web_config.get('port', 5000)
    
    # 检查HTTPS配置
    https_enabled = False
    if hasattr(app, 'https_config') and app.https_config['enabled'] and app.ssl_context:
        https_enabled = True
        https_config = app.https_config
    
    if https_enabled:
        # 双模式：同时启动HTTP和HTTPS服务器
        logging.info("启动双协议服务模式")
        logging.info(f"HTTP:  http://{http_host}:{http_port}")
        logging.info(f"HTTPS: https://{https_config['host']}:{https_config['port']}")
        logging.warning("注意：HTTPS使用自签名证书，浏览器会显示安全警告")
        
        # 在单独的线程中启动HTTPS服务器
        https_thread = threading.Thread(
            target=run_https_server,
            args=(app, https_config, app.ssl_context),
            daemon=False,  # 不使用daemon线程，确保HTTPS服务器稳定运行
            name="HTTPS-Server"
        )
        https_thread.start()
        
        # 等待HTTPS服务器启动
        time.sleep(3)  # 增加等待时间确保HTTPS服务器完全启动
        
        # 在主线程中启动HTTP服务器（生产环境不使用debug模式）
        logging.info("启动HTTP服务器（生产模式）")
        app.run(host=http_host, port=http_port, debug=False, threaded=True)
    else:
        # 仅HTTP模式
        logging.info(f"启动HTTP服务器: http://{http_host}:{http_port}")
        # 检查是否为开发环境
        is_development = os.environ.get('FLASK_ENV') == 'development'
        app.run(host=http_host, port=http_port, debug=is_development, threaded=True)
