"""PyInstaller runtime hook.

确保 Windows 便携版在用户直接双击 `VideoWhisper.exe` 时也能找到随包分发的 ffmpeg。
"""

import os
import sys


def _setup_ffmpeg_env() -> None:
    base_dir = os.path.dirname(sys.executable)
    ffmpeg_dir = os.path.join(base_dir, "ffmpeg")
    ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    if not os.path.exists(ffmpeg_exe):
        return

    os.environ.setdefault("FFMPEG_BINARY", ffmpeg_exe)
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


_setup_ffmpeg_env()
