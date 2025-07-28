import subprocess
import time
import requests
import sys
import os

def test_flask_startup():
    """测试Flask应用启动"""
    print("测试Flask应用启动...")
    
    # 检查app.py是否存在
    if not os.path.exists("app.py"):
        print("错误: app.py文件不存在")
        return False
    
    # 启动Flask应用
    print("启动Flask应用...")
    try:
        process = subprocess.Popen(
            [sys.executable, "app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print(f"Flask进程已启动，PID: {process.pid}")
        
        # 等待应用启动
        print("等待应用启动...")
        for i in range(30):  # 等待30秒
            try:
                response = requests.get("http://127.0.0.1:5000/login", timeout=2)
                if response.status_code == 200:
                    print("Flask应用启动成功!")
                    process.terminate()
                    return True
            except:
                pass
            time.sleep(1)
            print(f"等待中... ({i+1}/30)")
        
        # 如果超时，检查进程输出
        print("启动超时，检查进程输出...")
        try:
            stdout, stderr = process.communicate(timeout=5)
            if stdout:
                print(f"stdout: {stdout}")
            if stderr:
                print(f"stderr: {stderr}")
        except:
            pass
        
        process.terminate()
        print("Flask应用启动失败")
        return False
        
    except Exception as e:
        print(f"启动Flask应用时出错: {e}")
        return False

if __name__ == '__main__':
    test_flask_startup() 