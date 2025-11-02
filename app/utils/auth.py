from functools import wraps
from flask import request, jsonify
import os
from app.config.settings import Config


def _load_admin_token() -> str:
    """加载管理员令牌（可选）。优先环境变量，其次配置文件。
    未配置则返回空字符串，表示不启用鉴权（保持向后兼容）。
    """
    token = os.environ.get('ADMIN_TOKEN', '').strip()
    if token:
        return token
    try:
        cfg = Config.load_config() or {}
        sec = cfg.get('security') or {}
        token = str(sec.get('admin_token', '') or '').strip()
        return token
    except Exception:
        return ''


def _is_production() -> bool:
    """判断是否为生产环境。"""
    return os.environ.get('FLASK_ENV', '').strip().lower() == 'production'


def admin_protected(f):
    """破坏性接口的最小鉴权装饰器。
    - 当未配置 ADMIN_TOKEN 时，不启用校验（兼容旧行为）。
    - 当配置了 ADMIN_TOKEN 或 security.admin_token 时，要求请求头 `X-Admin-Token` 匹配。
    - 失败返回 403。
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _load_admin_token()
        # 生产环境强制需要令牌
        if not token and _is_production():
            return (
                jsonify(
                    {
                        'success': False,
                        'error': '权限错误',
                        'message': '生产环境需要配置ADMIN_TOKEN并在请求头提供X-Admin-Token',
                    }
                ),
                403,
            )

        # 开发环境未配置令牌：保持向后兼容直接放行
        if not token:
            return f(*args, **kwargs)

        # 校验令牌
        presented = request.headers.get('X-Admin-Token', '').strip()
        if not presented or presented != token:
            return (
                jsonify(
                    {
                        'success': False,
                        'error': '权限错误',
                        'message': '需要有效的管理员令牌',
                    }
                ),
                403,
            )
        return f(*args, **kwargs)

    return wrapper
