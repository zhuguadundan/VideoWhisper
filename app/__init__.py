from flask import Flask
from app.config.settings import Config

def create_app():
    app = Flask(__name__, 
                template_folder='../web/templates',
                static_folder='../web/static')
    
    app.config.from_object(Config)
    
    # 注册蓝图
    from app.main import main_bp
    app.register_blueprint(main_bp)
    
    return app