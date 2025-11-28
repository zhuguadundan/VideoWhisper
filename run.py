from app import create_app
from app.config.settings import Config
from app.utils.certificate_manager import CertificateManager, create_ssl_context
import threading
import time
import os
import logging


def run_http_server(app, host: str, port: int) -> None:
    """启动 HTTP 服务。"""
    logging.info(f"启动HTTP服务： http://{host}:{port}")
    # 启用多线程，避免长任务阻塞静态资源与 API 的快速响应
    app.run(host=host, port=port, debug=False, threaded=True)


def run_https_server(app, https_config: dict, ssl_context) -> None:
    """启动 HTTPS 服务。"""
    try:
        logging.info(
            f"启动HTTPS服务： https://{https_config['host']}:{https_config['port']}"
        )
        app.run(
            host=https_config["host"],
            port=https_config["port"],
            ssl_context=ssl_context,
            debug=False,  # 生产环境不使用 debug
            threaded=True,
        )
    except Exception as e:
        logging.error(f"HTTPS服务器启动失败: {e}")


if __name__ == "__main__":
    app = create_app()

    # 读取配置文件获取 web 设置
    config = Config.load_config()
    web_config = config.get("web", {})
    http_host = web_config.get("host", "0.0.0.0")
    http_port = web_config.get("port", 5000)

    # 检查 HTTPS 配置并按需准备证书与 SSL 上下文
    try:
        https_config = getattr(app, "https_config", None) or Config.get_https_config()
    except Exception:
        https_config = {"enabled": False}

    # 挂载 https_config，保持对外行为一致
    app.https_config = https_config

    https_enabled = False
    ssl_ctx = getattr(app, "ssl_context", None)

    if https_config.get("enabled"):
        if ssl_ctx is None:
            try:
                # 如配置允许，自动生成本地自签名证书（开发 / 简易部署场景）
                if https_config.get("auto_generate"):
                    mgr = CertificateManager(https_config)
                    mgr.ensure_certificates()

                cert_file = https_config.get("cert_file")
                key_file = https_config.get("key_file")
                if (
                    cert_file
                    and key_file
                    and os.path.exists(cert_file)
                    and os.path.exists(key_file)
                ):
                    ssl_ctx = create_ssl_context(cert_file, key_file)
                    app.ssl_context = ssl_ctx
            except Exception as e:
                logging.error(f"HTTPS 证书初始化失败，将仅使用 HTTP: {e}")

        if ssl_ctx is not None:
            https_enabled = True

    if https_enabled:
        # 双模式：同时启动 HTTP 和 HTTPS 服务
        logging.info("启动双协议服务模式")
        logging.info(f"HTTP:  http://{http_host}:{http_port}")
        logging.info(
            f"HTTPS: https://{https_config['host']}:{https_config['port']}"
        )
        logging.warning("注意：HTTPS 使用自签名证书，浏览器可能显示安全警告")

        # 在单独的线程中启动 HTTPS 服务
        https_thread = threading.Thread(
            target=run_https_server,
            args=(app, https_config, app.ssl_context),
            daemon=False,  # 不使用 daemon 线程，确保 HTTPS 服务器稳定运行
            name="HTTPS-Server",
        )
        https_thread.start()

        # 等待 HTTPS 服务器启动
        time.sleep(3)  # 增加等待时间确保 HTTPS 服务器完全启动

        # 在主线程中启动 HTTP 服务器（生产环境不使用 debug 模式）
        logging.info("启动HTTP服务器（生产模式）")
        app.run(host=http_host, port=http_port, debug=False, threaded=True)
    else:
        # 仅 HTTP 模式
        logging.info(f"启动HTTP服务： http://{http_host}:{http_port}")
        # 检查是否为开发环境
        is_development = os.environ.get("FLASK_ENV") == "development"
        app.run(host=http_host, port=http_port, debug=is_development, threaded=True)

