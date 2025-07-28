@echo off
echo 正在启动虚拟机克隆管理系统...
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

REM 启动应用
echo.
echo 启动完成！请访问: http://localhost:5000
echo 用户名: admin
echo 密码: 123456
echo.
echo 按 Ctrl+C 停止服务
echo.

python app.py

pause 