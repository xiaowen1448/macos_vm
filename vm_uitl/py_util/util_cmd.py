import paramiko
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *

def execute_ssh_command(host, username=None, password=None, command=None):
    """通过 SSH 执行命令"""
    if username is None:
        username = vm_username  # 使用全局配置的默认用户名
    if password is None:
        password = vm_password  # 使用全局配置的默认密码
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # 自动接受未知的主机密钥

    try:
        # 使用用户名和密码连接到远程主机
        client.connect(hostname=host, username=username, password=password, timeout=5)
        # 执行命令
        stdin, stdout, stderr = client.exec_command(command)
        # 获取命令输出
        output = stdout.read().decode()  # 获取命令输出
        error = stderr.read().decode()  # 获取错误输出
        if output:
            #print(f"输出:\n{output}")
            inum=1
        if error:
           # print(f"输出2:\n{output}")
           inum = 1

        return output, error

    except paramiko.AuthenticationException:
       # print("❌ SSH 认证失败，用户名或密码错误")
        return "", "认证失败"
    except paramiko.SSHException as e:
       # print(f"⚠️ SSH 连接错误: {e}")
        return "", f"SSH连接错误: {e}"
    except Exception as e:
        #print(f"❌ 连接失败: {e}")
        return "", f"连接失败: {e}"
    finally:
        client.close()

def get_default_ssh_config():
    """获取默认的SSH配置"""
    return {
        'username': vm_username,
        'password': vm_password,
        'timeout': 5
    }


