import yaml
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    
    @staticmethod
    def load_config():
        # 优先检查config文件夹中的配置文件，兼容Docker部署
        config_paths = [
            'config/config.yaml',     # Docker部署时的路径
            'config.yaml',            # 传统部署时的路径
        ]
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
        
        # 如果都找不到，抛出异常
        raise FileNotFoundError("未找到配置文件 config.yaml，请确保配置文件存在")
    
    @classmethod
    def get_api_config(cls, service):
        config = cls.load_config()
        return config['apis'].get(service, {})