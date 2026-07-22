# Build script for EasyConvert (Windows / PowerShell).
# Prerequisites:
#   pip install -r requirements.txt
#   ffmpeg.exe and ffprobe.exe placed next to this script
#     Download from https://github.com/BtbN/FFmpeg-Builds/releases
#     (ffmpeg-master-latest-win64-gpl.zip -> bin/ffmpeg.exe, bin/ffprobe.exe)
#
# Usage:
#   .\build.ps1
# Output:
#   dist\ogg_to_mp3.exe

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path "$here\ffmpeg.exe")) { throw "ffmpeg.exe not found in $here" }
if (-not (Test-Path "$here\ffprobe.exe")) { throw "ffprobe.exe not found in $here" }

pyinstaller --noconfirm --windowed --onefile `
  --icon "$here\ico.ico" `
  --name ogg_to_mp3 `
  --collect-all tkinterdnd2 `
  --collect-all imageio_ffmpeg `
  --collect-all pydub `
  --add-binary "$here\ffmpeg.exe;." `
  --add-binary "$here\ffprobe.exe;." `
  "$here\ogg_to_mp3.py"

Write-Host "Done. EXE: $here\dist\ogg_to_mp3.exe" -ForegroundColor Green
