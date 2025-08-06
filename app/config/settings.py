import yaml
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    
    @staticmethod
    def load_config():
        with open('config.yaml', 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    @classmethod
    def get_api_config(cls, service):
        config = cls.load_config()
        return config['apis'].get(service, {})