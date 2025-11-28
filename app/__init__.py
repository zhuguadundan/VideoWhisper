from flask import Flask, jsonify, request, g
from app.config.settings import Config
import logging
from logging.handlers import RotatingFileHandler
import traceback
import os
import uuid
try:
    from werkzeug.middleware.proxy_fix import ProxyFix
except Exception:
    ProxyFix = None


def create_app():
    app = Flask(
        __name__, template_folder='../web/templates', static_folder='../web/static'
    )

    app.config.from_object(Config)

    # 暴露 HTTPS 配置供外部使用（TLS 在容器入口处理）
    try:
        app.https_config = Config.get_https_config()
    except Exception:
        app.https_config = {'enabled': False}
    app.ssl_context = None
    # 可选：本地内嵌 TLS（仅开发用途）
    try:
        embed = str(os.environ.get('APP_EMBED_SSL', '')).strip().lower() in ("1", "true", "yes", "on")
        cert_file = os.environ.get('APP_EMBED_CERT', 'config/cert.pem')
        key_file = os.environ.get('APP_EMBED_KEY', 'config/key.pem')
        if embed and os.path.exists(cert_file) and os.path.exists(key_file):
            import ssl
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)
            app.ssl_context = ctx
            logging.info(f"启用本地内嵌 TLS（仅开发）：cert={cert_file}, key={key_file}")
            
    except Exception as _e:
        logging.warning(f"内嵌 TLS 初始化失败（忽略并继续 HTTP）：{_e}")

    # 代理透传与 HTTPS 语义保证（生产默认启用）
    try:
        use_proxy_fix = str(os.environ.get('USE_PROXY_FIX', 'true')).strip().lower() in ("1", "true", "yes", "on")
        if use_proxy_fix and ProxyFix is not None:
            app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    except Exception:
        pass

    try:
        # 默认不强制 https，避免本地纯 HTTP 开发场景行为突变；
        # 由容器/部署环境显式设置 FORCE_HTTPS_SCHEME=true 来开启
        force_https = str(os.environ.get('FORCE_HTTPS_SCHEME', 'false')).strip().lower() in ("1", "true", "yes", "on")
        if force_https:
            app.config['PREFERRED_URL_SCHEME'] = 'https'
            @app.before_request
            def _force_https_scheme():
                try:
                    ra = request.remote_addr or ''
                    if ra in ("127.0.0.1", "::1") or request.headers.get('X-Forwarded-Proto', '').lower() == 'https':
                        request.environ['wsgi.url_scheme'] = 'https'
                except Exception:
                    pass
    except Exception:
        pass

    # 日志
    os.makedirs('logs', exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = RotatingFileHandler(
        'logs/app.log', maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    root_logger.handlers = [file_handler, stream_handler]

    # 上传大小限制（优先环境变量）
    try:
        app_cfg = Config.load_config()
    except Exception:
        app_cfg = {}
    env_max_mb = os.environ.get('MAX_UPLOAD_SIZE_MB') or os.environ.get('UPLOAD_MAX_SIZE_MB')
    try:
        max_upload_mb = int(env_max_mb) if env_max_mb else int((app_cfg.get('upload') or {}).get('max_upload_size', 500))
    except Exception:
        max_upload_mb = 500
    app.config['MAX_CONTENT_LENGTH'] = max_upload_mb * 1024 * 1024

    # 启动时一次性安全提示（保持兼容）
    try:
        cfg = Config.load_config()
        sec = (cfg.get('security') or {})

        def _env_bool(name: str, default: bool) -> bool:
            val = os.environ.get(name)
            if val is None:
                return bool(default)
            return str(val).strip().lower() in ("1", "true", "yes", "on")

        allow_insecure = _env_bool('ALLOW_INSECURE_HTTP', sec.get('allow_insecure_http', True))
        allow_private = _env_bool('ALLOW_PRIVATE_ADDRESSES', sec.get('allow_private_addresses', True))
        if allow_insecure:
            logging.warning('安全提示：当前允许 HTTP 连接测试（开发兼容）。生产建议设置 ALLOW_INSECURE_HTTP=false 或在 config.yaml.security 中关闭')
        if allow_private:
            logging.warning('安全提示：当前允许访问私网/本地地址进行连接测试（开发兼容）。生产建议设置 ALLOW_PRIVATE_ADDRESSES=false 或在 config.yaml.security 中关闭')
    except Exception:
        pass

    def is_api_request():
        return request.path.startswith('/api/')

    @app.errorhandler(500)
    def _handle_internal_error_clean(e):
        logging.error(f"Internal Server Error: {str(e)}")
        logging.error(traceback.format_exc())
        if is_api_request():
            return (
                jsonify(
                    {
                        'success': False,
                        'error': '服务器内部错误',
                        'message': '系统出现内部错误，请稍后重试。如果问题持续存在，请联系管理员',
                    }
                ),
                500,
            )
        return ("<h1>服务器错误</h1><p>系统出现内部错误，请稍后重试</p>", 500)

    @app.errorhandler(404)
    def _handle_not_found_clean(e):
        if is_api_request():
            return (
                jsonify(
                    {
                        'success': False,
                        'error': '资源不存在',
                        'message': '请求的 API 端点不存在',
                    }
                ),
                404,
            )
        return ("<h1>页面未找到</h1><p>请求的页面不存在</p>", 404)

    @app.errorhandler(405)
    def _handle_method_not_allowed_clean(e):
        if is_api_request():
            return (
                jsonify(
                    {
                        'success': False,
                        'error': '请求方法不允许',
                        'message': '请求方法不被允许，请检查 HTTP 方法',
                    }
                ),
                405,
            )
        return ("<h1>请求方法不允许</h1><p>请求方法不被允许</p>", 405)

    @app.errorhandler(400)
    def _handle_bad_request_clean(e):
        if is_api_request():
            return (
                jsonify(
                    {
                        'success': False,
                        'error': '请求格式错误',
                        'message': '请求数据格式不正确，请检查请求参数',
                    }
                ),
                400,
            )
        return ("<h1>请求格式错误</h1><p>请求数据格式不正确</p>", 400)

    @app.errorhandler(Exception)
    def handle_exception(e):
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

        error_message = str(e)
        name = str(type(e).__name__)
        if 'Connection' in name:
            error_message = 'API 连接失败，请检查网络连接或 API 配置'
        elif 'timeout' in str(e).lower():
            error_message = '请求超时，请稍后重试'
        elif 'api_key' in str(e).lower() or 'unauthorized' in str(e).lower():
            error_message = 'API 密钥无效，请检查配置'
        elif 'file' in str(e).lower() and 'not found' in str(e).lower():
            error_message = '所需文件不存在，请检查文件路径'

        if is_api_request():
            msg = error_message if len(error_message) <= 200 else f"{error_message[:200]}..."
            return (
                jsonify(
                    {
                        'success': False,
                        'error': '系统异常',
                        'message': msg,
                        'error_type': type(e).__name__,
                    }
                ),
                500,
            )
        else:
            return (f"<h1>系统异常</h1><p>{error_message}</p>", 500)

    @app.before_request
    def _inject_request_id():
        try:
            g.request_id = request.headers.get('X-Request-Id') or uuid.uuid4().hex[:12]
        except Exception:
            g.request_id = uuid.uuid4().hex[:12]

    @app.after_request
    def _attach_request_id_header(resp):
        try:
            rid = getattr(g, 'request_id', None)
            if rid:
                resp.headers['X-Request-Id'] = rid
        except Exception:
            pass
        return resp

    @app.errorhandler(413)
    def _handle_request_entity_too_large_clean(e):
        if is_api_request():
            return (
                jsonify(
                    {
                        'success': False,
                        'error': '文件过大',
                        'message': f'文件大小超过限制（最大 {max_upload_mb}MB）',
                    }
                ),
                413,
            )
        return (f"<h1>文件过大</h1><p>文件大小超过限制（最大 {max_upload_mb}MB）</p>", 413)

    from app.main import main_bp
    app.register_blueprint(main_bp)

    return app
