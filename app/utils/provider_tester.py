"""
提供商连接测试帮助器（收敛 /api/test-connection 重复逻辑）
注意：不做 base_url 安全校验，调用方在路由层完成。
"""

from typing import Tuple, Optional


def test_siliconflow(api_key: str, base_url: Optional[str] = None, model: Optional[str] = None) -> Tuple[bool, str]:
    import requests
    base = (base_url or 'https://api.siliconflow.cn/v1').rstrip('/')
    headers = {'Authorization': f'Bearer {api_key}'}
    resp = requests.get(f"{base}/models", headers=headers, timeout=10)
    if resp.status_code == 200:
        return True, f'硅基流动API连接成功，模型: {model or ""}'
    return False, f'API响应错误: {resp.status_code}'


def test_openai_compatible(api_key: str, base_url: Optional[str] = None, model: Optional[str] = None) -> Tuple[bool, str]:
    try:
        import openai
    except Exception:
        raise ImportError('OpenAI库未安装，请先安装: pip install openai')

    client = openai.OpenAI(api_key=api_key, base_url=base_url if base_url else None)
    models = client.models.list()
    # 仅探活，不关心列表内容
    if not list(models):
        return False, '模型列表为空，请检查API密钥或Base URL'
    return True, f'OpenAI API连接成功，模型: {model or "未知"} (通过模型列表测试)'


def test_gemini(api_key: str, base_url: Optional[str] = None, model: Optional[str] = None) -> Tuple[bool, str]:
    try:
        import google.generativeai as genai
    except Exception:
        raise ImportError('Gemini库未安装，请先安装: pip install google-generativeai')

    import os
    if base_url:
        os.environ['GOOGLE_AI_STUDIO_API_URL'] = base_url
    genai.configure(api_key=api_key)
    mdl = genai.GenerativeModel(model or 'gemini-pro')
    _ = mdl.generate_content("Hello")
    return True, f'Gemini API连接成功，模型: {model or "gemini-pro"}'

