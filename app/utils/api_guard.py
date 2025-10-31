import os
import ipaddress
from urllib.parse import urlparse


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def is_safe_base_url(url: str, *,
                     allowed_hosts: list = None,
                     allow_http: bool = True,
                     allow_private: bool = True,
                     enforce_whitelist: bool = False) -> bool:
    try:
        if not url:
            return True
        p = urlparse(url)
        scheme = (p.scheme or '').lower()
        if scheme not in ('https', 'http'):
            return False
        if scheme == 'http' and not allow_http:
            return False
        host = p.hostname
        if not host:
            return False
        try:
            ip = ipaddress.ip_address(host)
            if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast) and not allow_private:
                return False
        except ValueError:
            if host.lower() in {'localhost'} and not allow_private:
                return False
        if enforce_whitelist and allowed_hosts:
            h = host.lower()
            if not any(h == w or h.endswith('.' + w) for w in allowed_hosts):
                return False
        return True
    except Exception:
        return False


def validate_runtime_api_config(api_config: dict):
    """校验运行时 API 配置中的 base_url。环境变量优先覆盖策略，保持向后兼容。"""
    if not isinstance(api_config, dict):
        return

    # 默认策略来自 config.yaml.security，但运行时用环境变量覆盖
    from app.config.settings import Config
    try:
        cfg = Config.load_config()
        sec = (cfg.get('security') or {})
        cfg_hosts = sec.get('allowed_api_hosts', []) or []
        env_hosts = [h.strip().lower() for h in os.environ.get('ALLOWED_API_HOSTS', '').split(',') if h.strip()]
        allowed_hosts = list({*(h.lower() for h in cfg_hosts if isinstance(h, str)), *env_hosts})
        allow_http = _env_bool('ALLOW_INSECURE_HTTP', bool(sec.get('allow_insecure_http', True)))
        allow_private = _env_bool('ALLOW_PRIVATE_ADDRESSES', bool(sec.get('allow_private_addresses', True)))
        enforce_whitelist = _env_bool('ENFORCE_API_HOSTS_WHITELIST', bool(sec.get('enforce_api_hosts_whitelist', False)))
    except Exception:
        allowed_hosts = []
        allow_http = True
        allow_private = True
        enforce_whitelist = False

    tp = (api_config.get('text_processor') or {})
    sf = (api_config.get('siliconflow') or {})
    for base_url in (tp.get('base_url'), sf.get('base_url')):
        if base_url and not is_safe_base_url(
            str(base_url),
            allowed_hosts=allowed_hosts,
            allow_http=allow_http,
            allow_private=allow_private,
            enforce_whitelist=enforce_whitelist,
        ):
            raise ValueError('不安全的Base URL，必须为HTTPS且非内网/本地地址')

