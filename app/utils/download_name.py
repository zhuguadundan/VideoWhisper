import re


def _clean_title(title: str, max_len: int = 60) -> str:
    if not title:
        return "视频"
    # 去扩展名样式片段
    title = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", title)
    # 替换非文件名安全字符
    title = re.sub(r"[^\w\u4e00-\u9fa5-]+", "_", title)
    title = title.strip("._ ")
    if len(title) > max_len:
        title = title[:max_len]
    return title or "视频"


def build_filename(title: str, kind: str, ext: str) -> str:
    """统一构造下载文件名。
    kind: transcript | summary | data | other
    ext: 不含点的扩展名
    """
    t = _clean_title(title)
    if kind == 'transcript':
        base = f"{t}_逐字稿"
    elif kind == 'summary':
        base = f"{t}_总结报告"
    elif kind == 'data':
        base = f"{t}_完整数据"
    else:
        base = f"{t}_{kind}"
    ext = (ext or '').lstrip('.').lower() or 'txt'
    return f"{base}.{ext}"

