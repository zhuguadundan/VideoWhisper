# VideoWhisper Windows 打包方案

> 目标：在 Windows 上提供无需安装 Python/FFmpeg 的一键运行版本，同时保持与现有 Docker / 传统部署完全兼容（Never break userspace）。

## 1. 场景与约束
- 目标用户：不会安装 Python / 不熟悉命令行的普通 Windows 用户。
- 应用形态：本地运行 Flask + Web 前端，通过浏览器访问（不强行上 Electron）。
- 兼容性：不修改现有 API、配置文件和目录结构，现有部署方式全部继续可用。
- 数据目录：继续使用当前的 `output/`、`temp/`、`logs/` 目录，保持路径语义不变。
- 打包形态：当前方案定位为**绿色版**（便携版），用户将 `VideoWhisper-win/` 解压到有写权限的目录（如桌面、文档、D 盘工作目录），目录本身即“项目根目录”。
- 路径与权限：不建议把 Windows 版安装到 `C:\Program Files\` 等只读目录，否则日志、输出文件以及 `config/.secret_key`、证书文件可能无法写入，导致运行异常。若未来需要安装器，将在后续方案中引入“程序目录 / 数据目录”分离。

## 2. 总体思路（实用主义方案）
1. 使用 PyInstaller 将 `run.py` 打包为 `VideoWhisper.exe`（单目录模式 one-folder，避免 one-file 带来的启动慢和调试困难）。
2. 将 `app/`、`web/`、`config.yaml` 等作为资源一起打进打包目录，不再把历史 `output/`、`temp/` 内容打入包内。
3. 在打包目录中内置精简版 Windows FFmpeg（仅 `ffmpeg/ffmpeg.exe`），并在启动脚本中通过 `PATH` 或环境变量 `FFMPEG_BINARY` 显式指向该可执行文件，保证 `ffmpeg-python` 能找到二进制，同时控制整体体积在 100MB 级别。
4. 提供一个简单的 `start_videowhisper.bat`，负责：
   - 启动 `VideoWhisper.exe`；
   - 简单等待数秒后，自动打开默认浏览器访问 `http://127.0.0.1:5000`。
5. 提供一键构建脚本 `win/build-full-win.ps1`，将「打包 + 内嵌 ffmpeg + 生成 zip」合并为单条命令，方便重复发版。
6. 可选：使用 Inno Setup 等工具进一步封装成安装程序（开始菜单快捷方式 + 卸载），但不作为本方案前提条件，后续按需设计。

## 3. 目标发行物结构（示例）
```text
VideoWhisper-win/
  VideoWhisper.exe              # PyInstaller 打包出的主程序
  start_videowhisper.bat        # 入口脚本，启动后延时几秒再打开浏览器
  config.yaml                   # Windows 版实际运行时配置（由 config.windows.yaml 复制生成）
  config.docker.yaml            # 备用/示例配置（只读）
  ffmpeg/
    ffmpeg.exe                  # 精简版 ffmpeg 主程序，仅此一个可执行文件
  logs/                         # 日志目录
  output/                       # 任务输出（运行时生成，可为空目录）
  temp/                         # 中间文件（运行时生成，可为空目录）
  app/                          # 后端代码
  web/                          # 前端静态文件
```

典型压缩包 `VideoWhisper-win.zip` 大小约 100MB 级别。

## 4. 构建流程（开发者视角）

### 4.1 环境准备
- Windows 10/11，x64。
- Python >= 3.10（与 yt-dlp 要求一致）。
- 已在当前仓库根目录执行过依赖安装：`pip install -r requirements.txt`。
- 额外安装：`pip install pyinstaller`。

### 4.2 打包前准备（配置文件）
- 仓库根目录已经提供 `config.windows.yaml`（内容基于当前 `config.yaml`，但做了如下调整，更适合本地桌面环境）：
  - `web.host: "127.0.0.1"`（只监听本机，避免意外暴露到局域网）。
  - `https.enabled: false`（默认关闭自签 HTTPS，避免浏览器警告和证书生成依赖）。
- 在构建脚本中会自动：
  - 备份当前 `config.yaml` 为 `config.yaml.bak.win`；
  - 使用 `config.windows.yaml` 覆盖生成用于打包的临时 `config.yaml`。
- 构建结束后会自动还原原始 `config.yaml`，服务器端 / Docker 部署不受影响。

### 4.3 基础打包脚本 `win/build-win.bat`
- 适用于只想快速生成 `VideoWhisper-win/` 目录（不自动打 zip）的场景，逻辑包括：
  - 切换到仓库根目录；
  - 备份并应用 `config.windows.yaml`；
  - 使用 PyInstaller 打包：
    ```bat
    %VENV% -m PyInstaller --name VideoWhisper --clean --noconfirm ^
      --add-data "app;app" ^
      --add-data "web;web" ^
      --add-data "config.yaml;." ^
      --add-data "config.docker.yaml;." ^
      run.py
    ```
    （注意：**不再**包含 `output;output` / `temp;temp`，避免历史任务文件进入分发包）
  - 将 `dist\VideoWhisper` 复制为 `VideoWhisper-win`；
  - 清空 `VideoWhisper-win\_internal\temp`，保证内部运行时 temp 目录是干净的；
  - 将 `win\start_videowhisper.bat` 复制到 `VideoWhisper-win\start_videowhisper.bat`。
- 此脚本不会自动下载 ffmpeg 和生成 zip，适合本地快速调试。

### 4.4 一键构建脚本 `win/build-full-win.ps1`
- 推荐用于正式发版，完整流程包括：
  1. 停止所有正在运行的 `VideoWhisper.exe` 进程；
  2. 清理旧的 `dist/`、`VideoWhisper-win/`、`VideoWhisper-win.zip`；
  3. 备份当前 `config.yaml`，并用 `config.windows.yaml` 覆盖生成临时配置；
  4. 调用 PyInstaller（参数同上，仅打包代码和配置）；
  5. 还原原始 `config.yaml`；
  6. 将 `dist/VideoWhisper` 复制为 `VideoWhisper-win`；
  7. 清空并重建 `VideoWhisper-win/_internal/temp` 目录；
  8. 复制 `win/start_videowhisper.bat` 到发布目录；
  9. 内嵌 ffmpeg（优先复用本机已安装的 `C:\ffmpeg\ffmpeg.exe` 或 PATH 中的 ffmpeg；若无则从官方仓库下载压缩包并提取 `bin/ffmpeg.exe` 到 `VideoWhisper-win/ffmpeg/`，同时移除 `ffplay.exe` / `ffprobe.exe` 控制体积）；
  10. 对 `VideoWhisper-win` 目录执行 `Compress-Archive` 生成最终分发包 `VideoWhisper-win.zip`（zip 内包含顶层 `VideoWhisper-win/` 目录，避免解压污染当前目录）。
- 使用方法（在仓库根目录）：
  ```powershell
  powershell -ExecutionPolicy Bypass -File win/build-full-win.ps1
  ```
- 运行完成后：
  - `VideoWhisper-win/` 为完整运行目录（约 200–300MB）；
  - `VideoWhisper-win.zip` 为可直接分发的压缩包（约 100MB 级）。

### 4.5 启动脚本
当前 `win/start_videowhisper.bat` 简化为“最笨但稳定”的版本：
```bat
@echo off
setlocal

set "PORT=5000"
set "EXE=VideoWhisper.exe"

rem ensure working directory is the folder of this script
cd /d "%~dp0" || (
  echo ERROR: failed to change directory to script location.
  pause
  exit /b 1
)

rem optional: use bundled ffmpeg if present
if exist "%~dp0ffmpeg\ffmpeg.exe" (
  echo Using bundled ffmpeg in %~dp0ffmpeg
  set "PATH=%~dp0ffmpeg;%PATH%"
  set "FFMPEG_BINARY=%~dp0ffmpeg\ffmpeg.exe"
)

if not exist "%EXE%" (
  echo ERROR: %EXE% not found in %CD%.
  echo Make sure you ran win\build-win.bat or win\build-full-win.ps1.
  pause
  exit /b 1
)

echo Starting %EXE% ...
start "VideoWhisper" "%EXE%"

echo Waiting a few seconds for server to start...
rem simple delay instead of complex port polling
timeout /t 8 /nobreak

echo Opening browser at http://127.0.0.1:%PORT%
start "" "http://127.0.0.1:%PORT%"

endlocal
exit /b 0
```

如遇某些环境的浏览器安全策略拦截 `start "" "http://127.0.0.1:%PORT%"`，可以在脚本中注释掉最后两行，让用户手动打开浏览器访问对应地址。

## 5. 与现有部署的兼容性（Never break userspace）
- 不移除、不修改现有的 Docker 部署脚本与传统部署流程，Windows 打包只是**新增**一种分发形态。
- 打包运行时的“项目根目录”即 `VideoWhisper-win/`，`Config.project_root()` 仍以代码位置推导：
  - `Config.load_config()` 继续从同级的 `config.yaml`（或 `config/config.yaml`）读取配置。
  - `system.temp_dir` / `system.output_dir` 等相对路径通过 `Config.resolve_path` 归一化到该目录下的 `temp/`、`output/`。
- `output/`、`temp/`、`logs/` 目录相对语义保持不变，老用户对这些目录的位置和含义不会被破坏。
- 构建脚本会在打包前清空 `_internal/temp`，但不会触及根目录下的 `output/`、`temp/` 及用户数据，只影响分发包内容。
- 如未来为了更好支持 PyInstaller 环境而在代码中增加 `sys._MEIPASS` 等路径兼容逻辑，必须保证：
  - 传统 Python 运行、Docker 容器内运行的行为不变。
  - 不改变现有配置文件搜索顺序和默认值，只在检测到打包环境时做附加分支。

## 6. 后续实现清单 / TODO

1. **在 CI/CD 中集成 `win/build-full-win.ps1`（可选）**
   - 如需自动发布 Windows 包，可在 GitHub Actions 或其他 CI 中增加步骤：
     - 安装 Python + 依赖；
     - 调用 `win/build-full-win.ps1`；
     - 将 `VideoWhisper-win.zip` 作为构建工件上传到 Release。

2. **在 README 中增加“Windows 桌面版”章节**
   - 简要说明：
     - 从 Release 下载 `VideoWhisper-win.zip`；
     - 解压后双击 `start_videowhisper.bat`；
     - 浏览器访问 `http://127.0.0.1:5000`。
   - 明确 ffmpeg 已随包内置，无需额外安装。

3. **（可选）安装器方案预研**
   - 若确有需求，再单独设计：
     - 使用 Inno Setup 等把程序安装到 `Program Files`，同时将数据目录放在 `%LOCALAPPDATA%\VideoWhisper`。
     - 在代码层面引入“程序目录 / 数据目录”概念，保证 Docker / 传统部署不受影响。

---

本方案的核心是：保持现有服务器端架构不变，只在最外层包一层 Windows 外壳，解决“安装和启动”这件事；同时通过清理临时目录和精简 ffmpeg，仅携带真正需要的二进制，把分发包控制在 100MB 级别。