param(
    [string]$TargetDir = "..\VideoWhisper-win\ffmpeg"
)

$ErrorActionPreference = "Stop"

function Resolve-TargetDir([string]$path) {
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
    return (Resolve-Path $path).ProviderPath
}

$TargetDir = Resolve-TargetDir $TargetDir

$ffmpegUrl   = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
$zipPath     = Join-Path $TargetDir "ffmpeg.zip"
$tempExtract = Join-Path ([System.IO.Path]::GetTempPath()) ("ffmpeg_embed_" + [guid]::NewGuid().ToString("N"))

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch {
}

Write-Host "[INFO] TargetDir: $TargetDir"

# Prefer system ffmpeg if available (avoids flaky downloads)
$destExe = Join-Path $TargetDir "ffmpeg.exe"
$systemCandidates = @(
    "C:\\ffmpeg\\ffmpeg.exe"
)
try {
    $cmd = Get-Command ffmpeg.exe -ErrorAction Stop
    if ($cmd -and $cmd.Source) { $systemCandidates += $cmd.Source }
} catch {
}

foreach ($c in ($systemCandidates | Select-Object -Unique)) {
    if ($c -and (Test-Path $c)) {
        Copy-Item $c $destExe -Force
        $srcDir = Split-Path -Parent $c
        # 如果 ffmpeg 依赖同目录 DLL，一并复制过来（没有则不会复制任何文件）
        Get-ChildItem $srcDir -File -Filter '*.dll' -ErrorAction SilentlyContinue | Copy-Item -Destination $TargetDir -Force -ErrorAction SilentlyContinue
        Write-Host "[INFO] Using system ffmpeg: $c"
        if (-not (Test-Path $destExe)) { throw "ffmpeg.exe missing after copy" }
        return
    }
}

Write-Host "[INFO] Downloading ffmpeg from $ffmpegUrl"

$downloadOk = $false
try {
    Start-BitsTransfer -Source $ffmpegUrl -Destination $zipPath -ErrorAction Stop
    $downloadOk = $true
} catch {
    Write-Host "[WARN] BITS download failed, fallback to Invoke-WebRequest"
}

if (-not $downloadOk) {
    for ($i = 1; $i -le 3; $i++) {
        try {
            Invoke-WebRequest -Uri $ffmpegUrl -OutFile $zipPath -UseBasicParsing
            $downloadOk = $true
            break
        } catch {
            if ($i -eq 3) { throw }
            Write-Host "[WARN] Download failed, retry $i/3..."
            Start-Sleep -Seconds (2 * $i)
        }
    }
}

if (-not $downloadOk) {
    throw "Failed to download ffmpeg archive"
}

Write-Host "[INFO] Extracting ffmpeg..."
if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
Expand-Archive -Path $zipPath -DestinationPath $tempExtract -Force

$folder = Get-ChildItem -Path $tempExtract -Directory | Select-Object -First 1
if (-not $folder) { throw "No extracted ffmpeg folder found in $tempExtract" }

$binPath = Join-Path $folder.FullName "bin"
if (-not (Test-Path $binPath)) { throw "ffmpeg bin folder not found: $binPath" }

# Copy all binaries from bin, then remove extras to keep size small
Copy-Item -Path (Join-Path $binPath "*") -Destination $TargetDir -Recurse -Force
foreach ($extra in @("ffplay.exe", "ffprobe.exe")) {
    $p = Join-Path $TargetDir $extra
    if (Test-Path $p) { Remove-Item $p -Force }
}

# Clean temp files
Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue

if (-not (Test-Path (Join-Path $TargetDir "ffmpeg.exe"))) {
    throw "ffmpeg.exe not found after embed"
}

Write-Host "[INFO] Embedded ffmpeg.exe to $TargetDir"