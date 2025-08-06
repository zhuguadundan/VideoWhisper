# FFmpeg 安装脚本
Write-Host "开始下载并安装 FFmpeg..." -ForegroundColor Green

# 设置下载URL和路径
$ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
$downloadPath = "$env:TEMP\ffmpeg.zip"
$extractPath = "$env:TEMP\ffmpeg"
$installPath = "C:\ffmpeg"

try {
    # 创建安装目录
    if (Test-Path $installPath) {
        Write-Host "FFmpeg 目录已存在，正在清理..." -ForegroundColor Yellow
        Remove-Item $installPath -Recurse -Force
    }
    New-Item -ItemType Directory -Path $installPath -Force | Out-Null

    # 下载 FFmpeg
    Write-Host "正在下载 FFmpeg..." -ForegroundColor Blue
    Invoke-WebRequest -Uri $ffmpegUrl -OutFile $downloadPath -UseBasicParsing
    Write-Host "下载完成！" -ForegroundColor Green

    # 解压文件
    Write-Host "正在解压文件..." -ForegroundColor Blue
    Expand-Archive -Path $downloadPath -DestinationPath $extractPath -Force

    # 找到解压后的文件夹
    $ffmpegFolder = Get-ChildItem -Path $extractPath -Directory | Select-Object -First 1
    $binPath = Join-Path $ffmpegFolder.FullName "bin"

    # 复制文件到安装目录
    Write-Host "正在安装 FFmpeg..." -ForegroundColor Blue
    Copy-Item -Path "$binPath\*" -Destination $installPath -Recurse -Force

    # 添加到系统 PATH
    Write-Host "正在添加到系统 PATH..." -ForegroundColor Blue
    $currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($currentPath -notlike "*$installPath*") {
        [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$installPath", "User")
        Write-Host "已添加到用户 PATH" -ForegroundColor Green
    } else {
        Write-Host "PATH 中已存在 FFmpeg 路径" -ForegroundColor Yellow
    }

    # 清理临时文件
    Write-Host "正在清理临时文件..." -ForegroundColor Blue
    Remove-Item $downloadPath -Force -ErrorAction SilentlyContinue
    Remove-Item $extractPath -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host "`nFFmpeg 安装完成！" -ForegroundColor Green
    Write-Host "安装路径: $installPath" -ForegroundColor Cyan
    Write-Host "`n请重新启动命令行窗口，然后运行 'ffmpeg -version' 测试安装" -ForegroundColor Yellow

} catch {
    Write-Host "安装过程中出现错误: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "请尝试以管理员身份运行此脚本" -ForegroundColor Yellow
}