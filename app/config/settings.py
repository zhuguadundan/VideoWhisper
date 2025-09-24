import yaml
import os
from dotenv import load_dotenv

load_dotenv()

# 计算项目根目录（以当前文件为锚点）
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    
    # 配置文件缓存
    _config_cache = None
    
    @classmethod
    def get_config(cls):
        if cls._config_cache is None:
            cls._config_cache = cls.load_config()
        return cls._config_cache

    @staticmethod
    def project_root() -> str:
        """返回项目根目录绝对路径"""
        return _PROJECT_ROOT

    @staticmethod
    def resolve_path(path: str) -> str:
        """将相对路径解析为基于项目根目录的绝对路径"""
        if not path:
            return path
        return path if os.path.isabs(path) else os.path.abspath(os.path.join(_PROJECT_ROOT, path))
    
    # HTTPS配置 - 优先使用环境变量，然后使用配置文件（默认启用HTTPS）
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
        """获取HTTPS配置，优先使用环境变量，然后使用配置文件（默认启用HTTPS）"""
        config = {}
        
        # 如果环境变量已设置，直接使用
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
            # 从配置文件读取
            app_config = cls.get_config()
            https_config = app_config.get('https', {})
            config['enabled'] = https_config.get('enabled', True)  # 默认启用
            config['port'] = https_config.get('port', 5443)
            config['host'] = https_config.get('host', '0.0.0.0')
            config['auto_generate'] = https_config.get('auto_generate', True)
            config['domain'] = https_config.get('domain', 'localhost')
            config['country'] = https_config.get('country', 'CN')
            config['state'] = https_config.get('state', 'Beijing')
            config['organization'] = https_config.get('organization', 'VideoWhisper Self-Signed')
            config['cert_file'] = https_config.get('cert_file', 'config/cert.pem')
            config['key_file'] = https_config.get('key_file', 'config/key.pem')
        
        # 证书路径解析为绝对路径（支持相对路径配置）
        config['cert_file'] = cls.resolve_path(config.get('cert_file', 'config/cert.pem'))
        config['key_file'] = cls.resolve_path(config.get('key_file', 'config/key.pem'))
        
        return config
    
    @staticmethod
    def load_config():
        # 以项目根目录为基准查找配置，兼容不同工作目录启动
        config_paths = [
            os.path.join(_PROJECT_ROOT, 'config', 'config.yaml'),
            os.path.join(_PROJECT_ROOT, 'config.yaml'),
        ]
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
        
        # 如果都找不到，抛出异常
        raise FileNotFoundError("未找到配置文件 config.yaml，请确保配置文件存在于项目根目录或 config/ 目录下")
    
    @classmethod
    def get_api_config(cls, service):
        config = cls.get_config()
        return (config.get('apis') or {}).get(service, {})