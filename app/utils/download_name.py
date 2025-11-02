import re


def build_filename(title: str, file_type: str, extension: str) -> str:
    """根据视频标题与类型生成统一的下载文件名。
    - 仅保留中文、字母、数字与空格
    - 移除已含扩展名
    - 限长20，空标题回退为“视频”
    """
    clean_title = title or ""
    # 去掉常见媒体扩展名
    clean_title = re.sub(r"\.(mp4|avi|mov|mkv|webm|flv|mp3|wav|aac|m4a|ogg)$", "", clean_title, flags=re.IGNORECASE)
    # 仅保留中文、字母、数字、空格和下划线
    clean_title = re.sub(r"[^\u4e00-\u9fa5\w\s]", "", clean_title).strip()
    if len(clean_title) > 20:
        clean_title = clean_title[:20]
    short_title = clean_title or "视频"

    type_map = {
        'transcript': '逐字稿',
        'summary': '总结报告',
        'data': '完整数据',
    }
    suffix = type_map.get(file_type, file_type)
    return f"{short_title}_{suffix}.{extension}"

