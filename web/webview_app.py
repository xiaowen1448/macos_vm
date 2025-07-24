import sys
import subprocess
import time
import requests
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QUrl

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("macos_vm管理平台")
        self.setGeometry(200, 100, 1200, 800)
        self.setMinimumSize(900, 600)
        self.setWindowIcon(QIcon("EFI/Clover/CLOVER/themes/logo_main.png"))
        self.browser = QWebEngineView()
        self.browser.load(QUrl("http://127.0.0.1:5000/login"))
        self.setCentralWidget(self.browser)

def wait_for_flask(url, timeout=30):
    for _ in range(timeout * 2):
        try:
            r = requests.get(url)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

if __name__ == '__main__':
    # 启动 Flask 服务
    flask_proc = subprocess.Popen([sys.executable, "app.py"])
    # 等待 Flask 启动
    if not wait_for_flask("http://127.0.0.1:5000/login"):
        print("Flask 服务未能在规定时间内启动。")
        flask_proc.terminate()
        sys.exit(1)
    # 启动桌面窗口
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec_()
    flask_proc.terminate()