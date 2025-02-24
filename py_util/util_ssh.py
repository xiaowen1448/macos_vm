import subprocess
def test_ssh_with_command(host, username):
    """使用系统 ssh 命令测试 SSH 登录"""
    try:
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", f"{username}@{host}", "exit"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return True
        else:
            return False
    except Exception as e:
        print(f"❌ 连接失败:")
    return False
# 示例调用
# test_ssh_with_command("192.168.1.100", "user")
