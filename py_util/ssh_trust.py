import os
import paramiko

# === 配置 ===
remote_host = "192.168.119.196"
remote_user = "wx"
remote_port = 22
key_path = os.path.expanduser("~/.ssh/id_rsa")
pub_key_path = key_path + ".pub"

# 1. 如果没有 SSH 密钥，生成它（调用系统 ssh-keygen）
if not os.path.exists(pub_key_path):
    os.system(f'ssh-keygen -t rsa -b 2048 -f "{key_path}" -N ""')

# 2. 读取公钥
with open(pub_key_path, 'r') as f:
    pub_key = f.read().strip()

# 3. 登录远程 macOS（第一次需密码）
#password = input(f"🔑 Enter password for {remote_user}@{remote_host}: ")
password = 123456
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=remote_host, port=remote_port, username=remote_user, password=password)

# 4. 添加公钥到远程 ~/.ssh/authorized_keys
commands = [
    'mkdir -p ~/.ssh',
    'chmod 700 ~/.ssh',
    f'echo "{pub_key}" >> ~/.ssh/authorized_keys',
    'chmod 600 ~/.ssh/authorized_keys'
]

for cmd in commands:
    stdin, stdout, stderr = client.exec_command(cmd)
    stdout.channel.recv_exit_status()  # 等待命令执行完

client.close()
print("✅ SSH key has been added. You can now SSH without password.")
