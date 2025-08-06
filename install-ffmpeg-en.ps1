# FFmpeg Installation Script
Write-Host "Starting FFmpeg installation..." -ForegroundColor Green

# Set paths
$ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
$downloadPath = "$env:TEMP\ffmpeg.zip"
$extractPath = "$env:TEMP\ffmpeg"
$installPath = "C:\ffmpeg"

try {
    # Create install directory
    if (Test-Path $installPath) {
        Write-Host "Removing existing FFmpeg directory..." -ForegroundColor Yellow
        Remove-Item $installPath -Recurse -Force
    }
    New-Item -ItemType Directory -Path $installPath -Force | Out-Null

    # Download FFmpeg
    Write-Host "Downloading FFmpeg..." -ForegroundColor Blue
    Invoke-WebRequest -Uri $ffmpegUrl -OutFile $downloadPath -UseBasicParsing
    Write-Host "Download completed!" -ForegroundColor Green

    # Extract files
    Write-Host "Extracting files..." -ForegroundColor Blue
    Expand-Archive -Path $downloadPath -DestinationPath $extractPath -Force

    # Find extracted folder
    $ffmpegFolder = Get-ChildItem -Path $extractPath -Directory | Select-Object -First 1
    $binPath = Join-Path $ffmpegFolder.FullName "bin"

    # Copy files to install directory
    Write-Host "Installing FFmpeg..." -ForegroundColor Blue
    Copy-Item -Path "$binPath\*" -Destination $installPath -Recurse -Force

    # Add to system PATH
    Write-Host "Adding to system PATH..." -ForegroundColor Blue
    $currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($currentPath -notlike "*$installPath*") {
        $newPath = "$currentPath;$installPath"
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
        Write-Host "Added to user PATH" -ForegroundColor Green
    } else {
        Write-Host "PATH already contains FFmpeg" -ForegroundColor Yellow
    }

    # Cleanup temp files
    Write-Host "Cleaning up temporary files..." -ForegroundColor Blue
    Remove-Item $downloadPath -Force -ErrorAction SilentlyContinue
    Remove-Item $extractPath -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host "`nFFmpeg installation completed!" -ForegroundColor Green
    Write-Host "Installation path: $installPath" -ForegroundColor Cyan
    Write-Host "`nPlease restart your command prompt and run 'ffmpeg -version' to test" -ForegroundColor Yellow

} catch {
    Write-Host "Error during installation: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Please try running as administrator" -ForegroundColor Yellow
}