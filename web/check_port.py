import socket
import subprocess
import sys

def check_port(port):
    """检查端口是否被占用"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('localhost', port))
            if result == 0:
                print(f"端口 {port} 已被占用")
                return True
            else:
                print(f"端口 {port} 可用")
                return False
    except Exception as e:
        print(f"检查端口时出错: {e}")
        return False

def find_process_using_port(port):
    """查找占用端口的进程"""
    try:
        # Windows命令
        cmd = f'netstat -ano | findstr :{port}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            print(f"占用端口 {port} 的进程:")
            print(result.stdout)
        else:
            print(f"没有找到占用端口 {port} 的进程")
    except Exception as e:
        print(f"查找进程时出错: {e}")

if __name__ == '__main__':
    port = 5000
    print(f"检查端口 {port} 状态...")
    
    if check_port(port):
        find_process_using_port(port)
    else:
        print("端口可用，可以启动Flask服务") 