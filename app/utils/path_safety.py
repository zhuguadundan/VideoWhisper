import os


def is_within(base: str, candidate: str) -> bool:
    """判断 candidate 是否严格位于 base 路径之内。
    基于 realpath + commonpath，防止路径遍历。
    """
    try:
        base_abs = os.path.realpath(base)
        cand_abs = os.path.realpath(candidate)
        return os.path.commonpath([base_abs]) == os.path.commonpath([base_abs, cand_abs])
    except Exception:
        return False


def safe_join(base: str, relative_path: str) -> str:
    """在 base 下拼接相对路径并进行越界校验，返回规范化的绝对路径。
    失败抛出 ValueError。
    """
    candidate = os.path.abspath(os.path.join(base, relative_path))
    if not is_within(base, candidate):
        raise ValueError("非法的文件路径")
    return candidate

