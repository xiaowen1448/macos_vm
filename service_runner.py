#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
macOS 虚拟机管理系统 - Windows 服务运行器

此脚本提供以下功能:
1. 将 Flask 应用作为 Windows 服务运行
2. 支持服务的安装、启动、停止、卸载
3. 后台运行，开机自启动
4. 服务日志记录

使用方法:
    python service_runner.py install    # 安装服务
    python service_runner.py start      # 启动服务
    python service_runner.py stop       # 停止服务
    python service_runner.py restart    # 重启服务
    python service_runner.py remove     # 卸载服务
    python service_runner.py debug      # 调试模式运行
"""

import os
import sys
import time
import logging
import threading
import subprocess
from pathlib import Path
from datetime import datetime

# 尝试导入 Windows 服务相关模块
try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    WINDOWS_SERVICE_AVAILABLE = True
except ImportError:
    WINDOWS_SERVICE_AVAILABLE = False
    print("警告: 无法导入 Windows 服务模块，将以普通进程方式运行")
    print("如需服务功能，请安装: pip install pywin32")

# 项目配置
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 服务配置
SERVICE_NAME = "macOSVMManager"
SERVICE_DISPLAY_NAME = "macOS 虚拟机管理系统"
SERVICE_DESCRIPTION = "macOS 虚拟机批量克隆和管理服务"

class MacOSVMService:
    """macOS 虚拟机管理服务类"""
    
    def __init__(self):
        self.flask_process = None
        self.running = False
        self.setup_logging()
    
    def setup_logging(self):
        """设置日志系统"""
        log_dir = PROJECT_ROOT / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f'service_{datetime.now().strftime("%Y-%m-%d")}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger('MacOSVMService')
    
    def start_flask_app(self):
        """启动 Flask 应用"""
        try:
            app_script = PROJECT_ROOT / 'app.py'
            if not app_script.exists():
                self.logger.error(f"Flask 应用脚本不存在: {app_script}")
                return False
            
            # 启动 Flask 应用进程
            cmd = [sys.executable, str(app_script)]
            self.flask_process = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            self.logger.info(f"Flask 应用已启动，PID: {self.flask_process.pid}")
            return True
            
        except Exception as e:
            self.logger.error(f"启动 Flask 应用失败: {e}")
            return False
    
    def stop_flask_app(self):
        """停止 Flask 应用"""
        if self.flask_process:
            try:
                self.flask_process.terminate()
                self.flask_process.wait(timeout=10)
                self.logger.info("Flask 应用已停止")
            except subprocess.TimeoutExpired:
                self.flask_process.kill()
                self.logger.warning("强制终止 Flask 应用")
            except Exception as e:
                self.logger.error(f"停止 Flask 应用时出错: {e}")
            finally:
                self.flask_process = None
    
    def start(self):
        """启动服务"""
        self.logger.info("正在启动 macOS 虚拟机管理服务...")
        
        if not self.start_flask_app():
            return False
        
        self.running = True
        self.logger.info("服务启动成功")
        
        # 监控 Flask 进程
        monitor_thread = threading.Thread(target=self.monitor_flask_process)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        return True
    
    def stop(self):
        """停止服务"""
        self.logger.info("正在停止 macOS 虚拟机管理服务...")
        
        self.running = False
        self.stop_flask_app()
        
        self.logger.info("服务已停止")
    
    def monitor_flask_process(self):
        """监控 Flask 进程状态"""
        while self.running:
            if self.flask_process and self.flask_process.poll() is not None:
                self.logger.warning("Flask 进程意外退出，尝试重启...")
                if self.running:  # 只有在服务运行状态下才重启
                    time.sleep(5)  # 等待 5 秒后重启
                    self.start_flask_app()
            
            time.sleep(30)  # 每 30 秒检查一次
    
    def run_debug(self):
        """调试模式运行"""
        print("🚀 以调试模式启动 macOS 虚拟机管理服务")
        print("按 Ctrl+C 停止服务")
        
        try:
            if self.start():
                while self.running:
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\n收到停止信号，正在关闭服务...")
        finally:
            self.stop()
            print("服务已停止")

# Windows 服务类
if WINDOWS_SERVICE_AVAILABLE:
    class WindowsService(win32serviceutil.ServiceFramework):
        """Windows 服务包装类"""
        
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION
        
        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            self.service = MacOSVMService()
        
        def SvcStop(self):
            """服务停止处理"""
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self.service.stop()
            win32event.SetEvent(self.hWaitStop)
        
        def SvcDoRun(self):
            """服务运行处理"""
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            
            if self.service.start():
                # 等待停止信号
                win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
            
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STOPPED,
                (self._svc_name_, '')
            )

def install_service():
    """安装 Windows 服务"""
    if not WINDOWS_SERVICE_AVAILABLE:
        print("❌ Windows 服务功能不可用，请安装 pywin32")
        return False
    
    try:
        win32serviceutil.InstallService(
            WindowsService._svc_reg_class_,
            WindowsService._svc_name_,
            WindowsService._svc_display_name_,
            description=WindowsService._svc_description_
        )
        print(f"✅ 服务 '{SERVICE_DISPLAY_NAME}' 安装成功")
        return True
    except Exception as e:
        print(f"❌ 服务安装失败: {e}")
        return False

def remove_service():
    """卸载 Windows 服务"""
    if not WINDOWS_SERVICE_AVAILABLE:
        print("❌ Windows 服务功能不可用")
        return False
    
    try:
        win32serviceutil.RemoveService(SERVICE_NAME)
        print(f"✅ 服务 '{SERVICE_DISPLAY_NAME}' 卸载成功")
        return True
    except Exception as e:
        print(f"❌ 服务卸载失败: {e}")
        return False

def start_service():
    """启动 Windows 服务"""
    if not WINDOWS_SERVICE_AVAILABLE:
        print("❌ Windows 服务功能不可用")
        return False
    
    try:
        win32serviceutil.StartService(SERVICE_NAME)
        print(f"✅ 服务 '{SERVICE_DISPLAY_NAME}' 启动成功")
        return True
    except Exception as e:
        print(f"❌ 服务启动失败: {e}")
        return False

def stop_service():
    """停止 Windows 服务"""
    if not WINDOWS_SERVICE_AVAILABLE:
        print("❌ Windows 服务功能不可用")
        return False
    
    try:
        win32serviceutil.StopService(SERVICE_NAME)
        print(f"✅ 服务 '{SERVICE_DISPLAY_NAME}' 停止成功")
        return True
    except Exception as e:
        print(f"❌ 服务停止失败: {e}")
        return False

def restart_service():
    """重启 Windows 服务"""
    print(f"🔄 重启服务 '{SERVICE_DISPLAY_NAME}'...")
    stop_service()
    time.sleep(2)
    return start_service()

def show_service_status():
    """显示服务状态"""
    if not WINDOWS_SERVICE_AVAILABLE:
        print("❌ Windows 服务功能不可用")
        return
    
    try:
        status = win32serviceutil.QueryServiceStatus(SERVICE_NAME)
        status_map = {
            win32service.SERVICE_STOPPED: "已停止",
            win32service.SERVICE_START_PENDING: "启动中",
            win32service.SERVICE_STOP_PENDING: "停止中",
            win32service.SERVICE_RUNNING: "运行中",
            win32service.SERVICE_CONTINUE_PENDING: "继续中",
            win32service.SERVICE_PAUSE_PENDING: "暂停中",
            win32service.SERVICE_PAUSED: "已暂停"
        }
        
        current_status = status_map.get(status[1], f"未知状态 ({status[1]})")
        print(f"📊 服务 '{SERVICE_DISPLAY_NAME}' 状态: {current_status}")
        
    except Exception as e:
        print(f"❌ 获取服务状态失败: {e}")

def show_help():
    """显示帮助信息"""
    help_text = f"""
🚀 macOS 虚拟机管理系统 - 服务运行器

用法: python {Path(__file__).name} [命令]

可用命令:
  install    安装 Windows 服务
  remove     卸载 Windows 服务
  start      启动服务
  stop       停止服务
  restart    重启服务
  status     查看服务状态
  debug      调试模式运行（前台运行）
  help       显示此帮助信息

示例:
  python {Path(__file__).name} install
  python {Path(__file__).name} start
  python {Path(__file__).name} debug

注意:
  - 安装/卸载服务需要管理员权限
  - 调试模式适合开发和测试
  - 服务模式适合生产环境

服务信息:
  名称: {SERVICE_NAME}
  显示名称: {SERVICE_DISPLAY_NAME}
  描述: {SERVICE_DESCRIPTION}
"""
    print(help_text)

def main():
    """主函数"""
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == 'install':
        install_service()
    elif command == 'remove':
        remove_service()
    elif command == 'start':
        start_service()
    elif command == 'stop':
        stop_service()
    elif command == 'restart':
        restart_service()
    elif command == 'status':
        show_service_status()
    elif command == 'debug':
        service = MacOSVMService()
        service.run_debug()
    elif command == 'help':
        show_help()
    else:
        print(f"❌ 未知命令: {command}")
        print("使用 'python service_runner.py help' 查看帮助")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # 如果没有参数，尝试作为 Windows 服务运行
        if WINDOWS_SERVICE_AVAILABLE:
            win32serviceutil.HandleCommandLine(WindowsService)
        else:
            show_help()
    else:
        main()