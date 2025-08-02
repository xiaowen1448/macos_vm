import subprocess
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *

def test_ssh_with_command(host, username=None):
    """使用系统 ssh 命令测试 SSH 登录"""
    if username is None:
        username = vm_username  # 使用全局配置的默认用户名
    
    try:
        result = subprocess.run(
            ["ssh",
             "-o","BatchMode=yes",
             "-o","StrictHostKeyChecking=no",
             f"{username}@{host}", "exit"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return True
        else:
            return ""
    except Exception as e:
        print(f"❌ 连接失败:")
    return ""

def get_default_ssh_credentials():
    """获取默认的SSH凭据"""
    return {
        'username': vm_username,
        'password': vm_password
    }

# 示例调用
# test_ssh_with_command("192.168.1.100", "user")
