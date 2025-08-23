from app import create_app
from app.config.settings import Config
import threading
import time

def run_http_server(app, host, port):
    """启动HTTP服务器"""
    print(f"启动HTTP服务器: http://{host}:{port}")
    app.run(host=host, port=port, debug=False)

def run_https_server(app, https_config, ssl_context):
    """启动HTTPS服务器"""
    print(f"启动HTTPS服务器: https://{https_config['host']}:{https_config['port']}")
    app.run(
        host=https_config['host'],
        port=https_config['port'],
        ssl_context=ssl_context,
        debug=False
    )

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
        print("启动双协议服务模式")
        print(f"HTTP:  http://{http_host}:{http_port}")
        print(f"HTTPS: https://{https_config['host']}:{https_config['port']}")
        print("注意：HTTPS使用自签名证书，浏览器会显示安全警告")
        
        # 在单独的线程中启动HTTPS服务器
        https_thread = threading.Thread(
            target=run_https_server,
            args=(app, https_config, app.ssl_context),
            daemon=True
        )
        https_thread.start()
        
        # 等待HTTPS服务器启动
        time.sleep(2)
        
        # 在主线程中启动HTTP服务器
        run_http_server(app, http_host, http_port)
    else:
        # 仅HTTP模式
        print(f"启动HTTP服务器: http://{http_host}:{http_port}")
        app.run(host=http_host, port=http_port, debug=True)