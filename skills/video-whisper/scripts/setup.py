#!/usr/bin/env python3
"""
video-whisper setup script
Automatically installs all dependencies (Python packages, ffmpeg, yt-dlp).
Works on Windows and Ubuntu/Debian.

Usage:
    python setup.py
    python setup.py --check   # Only check, don't install
"""

import subprocess
import sys
import shutil
import platform
import os
import argparse


def run(cmd, check=True, capture=False, shell=False):
    """Run a command and return result."""
    kwargs = {"check": check, "shell": shell}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    return subprocess.run(cmd, **kwargs)


def check_python_version():
    """yt-dlp >= 2025.10.22 requires Python >= 3.10"""
    v = sys.version_info
    if v < (3, 10):
        print(f"[FAIL] Python >= 3.10 required, got {v.major}.{v.minor}.{v.micro}")
        return False
    print(f"[OK] Python {v.major}.{v.minor}.{v.micro}")
    return True


def check_ffmpeg():
    """Check if ffmpeg is available."""
    path = shutil.which("ffmpeg")
    if path:
        try:
            r = run(["ffmpeg", "-version"], capture=True, check=False)
            first_line = (r.stdout or "").split("\n")[0].strip()
            print(f"[OK] ffmpeg found: {first_line}")
            return True
        except Exception:
            pass
    print("[MISS] ffmpeg not found")
    return False


def install_ffmpeg():
    """Install ffmpeg based on platform."""
    system = platform.system()

    if system == "Linux":
        print("[INFO] Installing ffmpeg via apt...")
        try:
            run(["sudo", "apt-get", "update", "-qq"], check=False)
            run(["sudo", "apt-get", "install", "-y", "-qq", "ffmpeg"])
            print("[OK] ffmpeg installed via apt")
            return True
        except Exception as e:
            print(f"[FAIL] apt install failed: {e}")
            return False

    elif system == "Darwin":
        print("[INFO] Installing ffmpeg via brew...")
        try:
            run(["brew", "install", "ffmpeg"])
            print("[OK] ffmpeg installed via brew")
            return True
        except Exception as e:
            print(f"[FAIL] brew install failed: {e}")
            print("[HINT] Install Homebrew first: https://brew.sh")
            return False

    elif system == "Windows":
        # Try winget first, then choco
        for mgr, cmd in [
            ("winget", ["winget", "install", "--id", "Gyan.FFmpeg", "-e", "--accept-source-agreements", "--accept-package-agreements"]),
            ("choco", ["choco", "install", "ffmpeg", "-y"]),
        ]:
            if shutil.which(mgr):
                print(f"[INFO] Installing ffmpeg via {mgr}...")
                try:
                    run(cmd)
                    print(f"[OK] ffmpeg installed via {mgr}")
                    return True
                except Exception as e:
                    print(f"[WARN] {mgr} install failed: {e}")

        print("[FAIL] Cannot auto-install ffmpeg on Windows.")
        print("[HINT] Options:")
        print("  1. winget install Gyan.FFmpeg")
        print("  2. choco install ffmpeg")
        print("  3. Download from https://www.gyan.dev/ffmpeg/builds/")
        print("     Extract and add bin/ to PATH")
        return False

    else:
        print(f"[FAIL] Unsupported platform: {system}")
        return False


def check_pip_packages():
    """Check if required Python packages are installed."""
    req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    if not os.path.exists(req_file):
        print(f"[WARN] requirements.txt not found at {req_file}")
        return False

    # Quick check: try importing key modules
    missing = []
    for mod_name, pip_name in [
        ("yt_dlp", "yt-dlp"),
        ("openai", "openai"),
        ("requests", "requests"),
        ("yaml", "pyyaml"),
        ("ffmpeg", "ffmpeg-python"),
    ]:
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pip_name)

    if not missing:
        print("[OK] All Python packages installed")
        return True

    print(f"[MISS] Missing Python packages: {', '.join(missing)}")
    return False


def install_pip_packages():
    """Install Python packages from requirements.txt."""
    req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    print(f"[INFO] Installing Python packages from {req_file}...")
    try:
        run([sys.executable, "-m", "pip", "install", "-r", req_file, "-q"])
        print("[OK] Python packages installed")
        return True
    except Exception as e:
        print(f"[FAIL] pip install failed: {e}")
        return False


def check_api_key():
    """Check if SiliconFlow API key is configured."""
    key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    if key:
        print(f"[OK] SILICONFLOW_API_KEY set ({key[:8]}...)")
        return True
    print("[WARN] SILICONFLOW_API_KEY not set (needed at runtime)")
    print("[HINT] Set it: export SILICONFLOW_API_KEY=sk-xxx  (Linux/Mac)")
    print("              set SILICONFLOW_API_KEY=sk-xxx      (Windows cmd)")
    print("              $env:SILICONFLOW_API_KEY='sk-xxx'   (PowerShell)")
    return False


def main():
    parser = argparse.ArgumentParser(description="Setup video-whisper dependencies")
    parser.add_argument("--check", action="store_true", help="Only check, don't install")
    args = parser.parse_args()

    print("=" * 50)
    print("video-whisper Setup")
    print("=" * 50)
    print()

    all_ok = True

    # 1. Python version
    if not check_python_version():
        print("\n[FATAL] Python >= 3.10 is required. Please upgrade.")
        sys.exit(1)

    # 2. ffmpeg
    if not check_ffmpeg():
        if args.check:
            all_ok = False
        else:
            if not install_ffmpeg():
                all_ok = False
            elif not check_ffmpeg():
                all_ok = False

    # 3. Python packages
    if not check_pip_packages():
        if args.check:
            all_ok = False
        else:
            if not install_pip_packages():
                all_ok = False

    # 4. API key (always just check)
    check_api_key()

    print()
    if all_ok:
        print("=" * 50)
        print("[OK] All dependencies ready!")
        print("=" * 50)
    else:
        print("=" * 50)
        print("[WARN] Some dependencies missing. Fix above issues.")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()
