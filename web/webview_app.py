

import sys
import subprocess
import time
import requests
import logging
import os
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QUrl

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('webview_debug.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("初始化主窗口")
        self.setWindowTitle("macos_vm管理平台")
        self.setGeometry(200, 100, 1200, 800)
        self.setMinimumSize(900, 600)
        
        # 设置窗口图标
        icon_path = "EFI/Clover/CLOVER/themes/logo_main.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            logger.debug(f"设置窗口图标: {icon_path}")
        else:
            logger.warning(f"窗口图标文件不存在: {icon_path}")
        
        self.browser = QWebEngineView()
        login_url = "http://127.0.0.1:5000/login"
        logger.debug(f"加载登录页面: {login_url}")
        self.browser.load(QUrl(login_url))
        self.setCentralWidget(self.browser)
        logger.info("主窗口初始化完成")

def wait_for_flask(url, timeout=30):
    logger.info(f"等待Flask服务启动: {url}")
    for i in range(timeout * 2):
        try:
            logger.debug(f"尝试连接Flask服务 (第{i+1}次)")
            r = requests.get(url)
            if r.status_code == 200:
                logger.info("Flask服务启动成功")
                return True
        except Exception as e:
            logger.debug(f"连接失败: {str(e)}")
        time.sleep(0.5)
    logger.error(f"Flask服务在{timeout}秒内未能启动")
    return False

if __name__ == '__main__':
    logger.info("启动macos_vm管理平台")
    
    # 启动 Flask 服务
    logger.info("启动Flask服务")
    flask_proc = subprocess.Popen([sys.executable, "app.py"])
    
    # 等待 Flask 启动
    if not wait_for_flask("http://127.0.0.1:5000/login"):
        logger.error("Flask 服务未能在规定时间内启动")
        flask_proc.terminate()
        sys.exit(1)
    
    # 启动桌面窗口
    logger.info("启动桌面窗口")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    logger.info("桌面窗口显示完成")
    
    # 运行应用
    logger.info("开始运行应用")
    app.exec_()
    
    # 清理资源
    logger.info("应用退出，清理资源")
    flask_proc.terminate()