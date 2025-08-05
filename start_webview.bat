@echo off
echo 正在启动macos_vm管理平台(WebView版本)...
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

REM 安装依赖
echo 正在安装依赖...
pip install -r requirements.txt

REM 启动WebView应用
echo.
echo 启动WebView应用...
echo 这将启动一个桌面窗口来访问管理平台
echo.
echo 按 Ctrl+C 停止服务
echo.

python webview_app.py

pause 