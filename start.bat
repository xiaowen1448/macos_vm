@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   macOS 虚拟机管理系统 - Web版本
echo ========================================
echo.

REM 检查管理员权限
net session >nul 2>&1
if %errorlevel% == 0 (
    echo ✅ 以管理员权限运行
) else (
    echo ⚠️  建议以管理员权限运行以获得最佳体验
)

echo 🔍 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到Python环境
    echo 请确保已安装Python 3.7或更高版本
    echo 下载地址: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✅ Python版本: !PYTHON_VERSION!

echo 🔍 检查Python版本兼容性...
python -c "import sys; exit(0 if sys.version_info >= (3, 7) else 1)" >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: Python版本过低
    echo 当前版本: !PYTHON_VERSION!
    echo 需要版本: 3.7或更高
    echo.
    pause
    exit /b 1
)

echo 📦 检查并安装依赖包...
if exist requirements.txt (
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo ⚠️  警告: 部分依赖包安装可能存在问题
        echo 尝试升级pip并重新安装...
        python -m pip install --upgrade pip --quiet
        pip install -r requirements.txt
        if errorlevel 1 (
            echo ❌ 依赖包安装失败，请检查网络连接
            echo 或手动运行: pip install -r requirements.txt
            pause
            exit /b 1
        )
    )
    echo ✅ 依赖包检查完成
) else (
    echo ⚠️  未找到requirements.txt文件
)

echo 🔍 检查配置文件...
if exist config.py (
    echo ✅ 配置文件存在
) else (
    echo ⚠️  未找到config.py配置文件
    echo 请确保配置文件存在并正确配置
)

echo 🔍 检查应用文件...
if exist app.py (
    echo ✅ 应用文件存在
) else (
    echo ❌ 错误: 未找到app.py文件
    echo 请确保在正确的目录中运行此脚本
    pause
    exit /b 1
)

echo.
echo 🚀 启动Flask应用...
echo ========================================
echo 📱 访问地址: http://localhost:5000
echo 👤 默认用户名: admin
echo 🔑 默认密码: 123456
echo ========================================
echo.
echo 💡 提示:
echo   - 按Ctrl+C停止服务
echo   - 如需后台运行，请使用service_runner.py
echo   - 如需桌面版本，请运行start_webview.bat
echo.
echo ⏳ 正在启动，请稍候...
echo.

REM 启动应用并捕获错误
python app.py
set APP_EXIT_CODE=%errorlevel%

echo.
if %APP_EXIT_CODE% == 0 (
    echo ✅ 应用正常退出
) else (
    echo ❌ 应用异常退出，错误代码: %APP_EXIT_CODE%
    echo 请检查logs目录中的日志文件获取详细信息
)

echo.
echo 按任意键退出...
pause >nul