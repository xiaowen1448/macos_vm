@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   macOS 虚拟机管理系统 - 桌面版本
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

echo 🔍 检查PyQt5依赖...
python -c "import PyQt5" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  PyQt5未安装，正在安装...
    pip install PyQt5 PyQtWebEngine --quiet
    if errorlevel 1 (
        echo ❌ PyQt5安装失败
        echo 请手动安装: pip install PyQt5 PyQtWebEngine
        pause
        exit /b 1
    )
    echo ✅ PyQt5安装完成
) else (
    echo ✅ PyQt5已安装
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
if exist webview_app.py (
    echo ✅ 桌面应用文件存在
) else (
    echo ❌ 错误: 未找到webview_app.py文件
    echo 请确保在正确的目录中运行此脚本
    pause
    exit /b 1
)

echo.
echo 🚀 启动桌面应用...
echo ========================================
echo 🖥️  桌面版本 - 集成WebView界面
echo 👤 默认用户名: admin
echo 🔑 默认密码: 123456
echo ========================================
echo.
echo 💡 提示:
 echo   - 关闭窗口即可退出应用
echo   - 如需Web版本，请运行start.bat
echo   - 如需后台服务，请使用service_runner.py
echo.
echo ⏳ 正在启动桌面应用，请稍候...
echo.

REM 启动桌面应用并捕获错误
python webview_app.py
set APP_EXIT_CODE=%errorlevel%

echo.
if %APP_EXIT_CODE% == 0 (
    echo ✅ 应用正常退出
) else (
    echo ❌ 应用异常退出，错误代码: %APP_EXIT_CODE%
    echo 请检查logs目录中的日志文件获取详细信息
    echo.
    echo 常见问题解决方案:
    echo   1. 确保PyQt5正确安装: pip install PyQt5 PyQtWebEngine
    echo   2. 检查显示器设置和分辨率
    echo   3. 尝试以管理员权限运行
)

echo.
echo 按任意键退出...
pause >nul