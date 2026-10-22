@echo off
chcp 65001 >nul
echo FrameCheck - 安装视频解码依赖
echo.
echo 本脚本使用 Windows 的 winget 安装 Gyan.FFmpeg。
echo 不上传视频。安装器如显示许可或系统确认，请阅读后自行决定。
echo.
where winget >nul 2>&1
if errorlevel 1 (
  echo 未找到 winget。请从 https://ffmpeg.org/download.html 获取 Windows 版本。
  echo 解压后在 FrameCheck 中选择 ffmpeg.exe，ffprobe.exe 应位于同一目录。
  pause
  exit /b 1
)
choice /c YN /m "是否继续安装 FFmpeg？"
if errorlevel 2 exit /b 0
winget install --id Gyan.FFmpeg --exact --source winget
if errorlevel 1 (
  echo.
  echo winget 未确认安装成功；如提示已安装，可回到 FrameCheck 点击“检查环境”。
  echo 仍找不到时，在软件中手动选择已有的 ffmpeg.exe。
  pause
  exit /b 1
)
echo.
echo 安装完成。返回 FrameCheck，点击“检查环境”或“运行内置示例”。
pause
