param(
    [string]$ConfigTemplate = "config.windows.yaml",
    [string]$AppName        = "VideoWhisper",
    [string]$DistDir        = "dist",
    [string]$OutDir         = "VideoWhisper-win",
    [string]$ZipName        = "VideoWhisper-win.zip"
)

$ErrorActionPreference = "Stop"

Write-Host "[INFO] ==== Build full Windows package ===="

# 1) 结束可能在运行的进程
Write-Host "[INFO] Stopping running processes..."
Get-Process $AppName -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# 2) 清理旧输出
Write-Host "[INFO] Cleaning old dist/out/zip..."
if (Test-Path $DistDir) { Remove-Item $DistDir -Recurse -Force }
if (Test-Path $OutDir)  { Remove-Item $OutDir  -Recurse -Force }
if (Test-Path $ZipName) { Remove-Item $ZipName -Force }

# 3) 备份并切换到 Windows 配置
if (Test-Path 'config.yaml') {
    Write-Host "[INFO] Backup config.yaml -> config.yaml.bak.win"
    Copy-Item 'config.yaml' 'config.yaml.bak.win' -Force
}
if (Test-Path $ConfigTemplate) {
    Write-Host "[INFO] Use template $ConfigTemplate as build-time config.yaml"
    Copy-Item $ConfigTemplate 'config.yaml' -Force
}

# 4) 运行 PyInstaller，仅打包代码与配置
Write-Host "[INFO] Running PyInstaller..."
.venv\Scripts\python.exe -m PyInstaller `
  --name $AppName `
  --clean --noconfirm `
  --runtime-hook "win\\pyi_rth_ffmpeg_path.py" `
  --add-data "app;app" `
  --add-data "web;web" `
  --add-data "config.yaml;." `
  --add-data "config.docker.yaml;." `
  run.py

$code = $LASTEXITCODE

# 5) 还原 config.yaml
if (Test-Path 'config.yaml.bak.win') {
    Write-Host "[INFO] Restore original config.yaml"
    Move-Item 'config.yaml.bak.win' 'config.yaml' -Force
}

if ($code -ne 0) {
    throw "PyInstaller failed with exit code $code"
}

# 6) 构建发布目录
$distPath = Join-Path $DistDir $AppName
if (-not (Test-Path $distPath)) {
    throw "Expected dist/$AppName not found after build"
}
Write-Host "[INFO] Copy dist/$AppName -> $OutDir"
Copy-Item $distPath $OutDir -Recurse -Force

# 7) 清空 _internal/temp，避免历史任务进入分发包
$internalTemp = Join-Path $OutDir "_internal\temp"
if (Test-Path $internalTemp) {
    Write-Host "[INFO] Clean $internalTemp"
    Remove-Item $internalTemp -Recurse -Force
}
New-Item -ItemType Directory -Path $internalTemp -Force | Out-Null

# 8) 复制启动脚本
if (Test-Path "win\start_videowhisper.bat") {
    Write-Host "[INFO] Copy start_videowhisper.bat -> $OutDir"
    Copy-Item "win\start_videowhisper.bat" (Join-Path $OutDir "start_videowhisper.bat") -Force
}

# 9) 嵌入 ffmpeg，仅保留 ffmpeg.exe
Write-Host "[INFO] Embedding ffmpeg (ffmpeg.exe only)..."
$embedScript = Join-Path $PSScriptRoot "embed-ffmpeg.ps1"
& $embedScript -TargetDir (Join-Path $OutDir "ffmpeg")
if (-not (Test-Path (Join-Path $OutDir "ffmpeg\ffmpeg.exe"))) {
    throw "ffmpeg.exe missing after embed"
}

# 10) 生成压缩包
Write-Host "[INFO] Creating $ZipName..."
if (Test-Path $ZipName) { Remove-Item $ZipName -Force }
Compress-Archive -Path $OutDir -DestinationPath $ZipName -Force

Write-Host "[INFO] Build full Windows package completed: $ZipName"
