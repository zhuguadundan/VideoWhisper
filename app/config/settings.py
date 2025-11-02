import yaml
import os
import logging
import secrets
from dotenv import load_dotenv

load_dotenv()

# 项目根目录（以当前文件为基准）
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _resolve_secret_key() -> str:
    """Resolve Flask SECRET_KEY with fallbacks.
    Priority: env SECRET_KEY (if not 'dev-secret-key') -> config/.secret_key -> auto-generate.
    """
    try:
        env_key = os.environ.get('SECRET_KEY')
        if env_key and env_key != 'dev-secret-key':
            return env_key

        secret_path = os.path.join(_PROJECT_ROOT, 'config', '.secret_key')
        if os.path.exists(secret_path):
            try:
                with open(secret_path, 'r', encoding='utf-8') as f:
                    key = (f.read() or '').strip()
                    if key:
                        if not env_key:
                            logging.warning("SECRET_KEY 未通过环境变量提供，已从 config/.secret_key 加载")
                        return key
            except Exception as e:
                logging.error(f"读取持久化 SECRET_KEY 失败: {e}")

        try:
            os.makedirs(os.path.dirname(secret_path), exist_ok=True)
            key = secrets.token_hex(32)
            with open(secret_path, 'w', encoding='utf-8') as f:
                f.write(key)
            try:
                os.chmod(secret_path, 0o600)
            except Exception:
                pass
            logging.warning("SECRET_KEY 未显式设置，已自动生成并保存在 config/.secret_key（建议在生产设置环境变量 SECRET_KEY）")
            return key
        except Exception as e:
            logging.error(f"生成/持久化 SECRET_KEY 失败，将使用临时 key: {e}")
            try:
                tmp_key = secrets.token_hex(32)
                logging.warning("使用临时 SECRET_KEY，重启后会话将失效。建议配置环境变量或确保 config/.secret_key 可写")
                return tmp_key
            except Exception:
                return 'dev-secret-key'
    except Exception as e:
        logging.error(f"SECRET_KEY 回退流程异常: {e}")
        return 'dev-secret-key'


class Config:
    SECRET_KEY = _resolve_secret_key()

    _config_cache = None

    @classmethod
    def get_config(cls):
        if cls._config_cache is None:
            try:
                cls._config_cache = cls.load_config()
            except Exception:
                cls._config_cache = {}
        return cls._config_cache

    @staticmethod
    def project_root() -> str:
        return _PROJECT_ROOT

    @staticmethod
    def resolve_path(path: str) -> str:
        if not path:
            return path
        return path if os.path.isabs(path) else os.path.abspath(os.path.join(_PROJECT_ROOT, path))

    # Legacy class attributes (kept for compatibility; get_https_config is preferred)
    HTTPS_ENABLED = os.environ.get('HTTPS_ENABLED', 'true').lower() == 'true'
    HTTPS_PORT = int(os.environ.get('HTTPS_PORT', '5443'))
    HTTPS_HOST = os.environ.get('HTTPS_HOST', '0.0.0.0')
    CERT_FILE = os.environ.get('CERT_FILE', 'config/cert.pem')
    KEY_FILE = os.environ.get('KEY_FILE', 'config/key.pem')
    CERT_AUTO_GENERATE = os.environ.get('CERT_AUTO_GENERATE', 'true').lower() == 'true'
    CERT_DOMAIN = os.environ.get('CERT_DOMAIN', 'localhost')
    CERT_COUNTRY = os.environ.get('CERT_COUNTRY', 'CN')
    CERT_STATE = os.environ.get('CERT_STATE', 'Beijing')
    CERT_ORGANIZATION = os.environ.get('CERT_ORGANIZATION', 'VideoWhisper Self-Signed')
    @classmethod
    def get_https_config(cls):
        config = {}
        env_https_enabled = os.environ.get('HTTPS_ENABLED', '').lower()
        if env_https_enabled:
            config['enabled'] = env_https_enabled == 'true'
            config['port'] = int(os.environ.get('HTTPS_PORT', '5443'))
            config['host'] = os.environ.get('HTTPS_HOST', '0.0.0.0')
            config['auto_generate'] = os.environ.get('CERT_AUTO_GENERATE', 'true').lower() == 'true'
            config['domain'] = os.environ.get('CERT_DOMAIN', 'localhost')
            config['country'] = os.environ.get('CERT_COUNTRY', 'CN')
            config['state'] = os.environ.get('CERT_STATE', 'Beijing')
            config['organization'] = os.environ.get('CERT_ORGANIZATION', 'VideoWhisper Self-Signed')
            config['cert_file'] = os.environ.get('CERT_FILE', 'config/cert.pem')
            config['key_file'] = os.environ.get('KEY_FILE', 'config/key.pem')
        else:
            try:
                app_config = cls.get_config()
                https_config = (app_config or {}).get('https', {})
            except Exception:
                https_config = {}
            config['enabled'] = https_config.get('enabled', True)
            config['port'] = https_config.get('port', 5443)
            config['host'] = https_config.get('host', '0.0.0.0')
            config['auto_generate'] = https_config.get('auto_generate', True)
            config['domain'] = https_config.get('domain', 'localhost')
            config['country'] = https_config.get('country', 'CN')
            config['state'] = https_config.get('state', 'Beijing')
            config['organization'] = https_config.get('organization', 'VideoWhisper Self-Signed')
            config['cert_file'] = https_config.get('cert_file', 'config/cert.pem')
            config['key_file'] = https_config.get('key_file', 'config/key.pem')
        config['cert_file'] = cls.resolve_path(config.get('cert_file', 'config/cert.pem'))
        config['key_file'] = cls.resolve_path(config.get('key_file', 'config/key.pem'))
        return config
    @staticmethod
    def load_config():
        config_paths = [
            os.path.join(_PROJECT_ROOT, 'config', 'config.yaml'),
            os.path.join(_PROJECT_ROOT, 'config.yaml'),
        ]
        for config_path in config_paths:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
        raise FileNotFoundError('未找到配置文件 config.yaml，请将配置文件放在项目根目录或 config/ 目录下')

    @classmethod
    def get_api_config(cls, service):
        try:
            config = cls.get_config() or {}
        except Exception:
            config = {}
        return (config.get('apis') or {}).get(service, {})
