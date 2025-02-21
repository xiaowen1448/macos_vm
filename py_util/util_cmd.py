import paramiko


def execute_ssh_command(host, username, command):
    """通过 SSH 执行命令"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # 自动接受未知的主机密钥

    try:
        # 使用用户名和密码连接到远程主机
        client.connect(hostname=host, username=username, timeout=5)

        # 执行命令
        stdin, stdout, stderr = client.exec_command(command)

        # 获取命令输出
        output = stdout.read().decode()  # 获取命令输出
        error = stderr.read().decode()  # 获取错误输出

        if output:
            print(f"输出:\n{output}")
        if error:
            print(f"错误:\n{error}")

        return output, error

    except paramiko.AuthenticationException:
        print("❌ SSH 认证失败，用户名或密码错误")
    except paramiko.SSHException as e:
        print(f"⚠️ SSH 连接错误: {e}")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
    finally:
        client.close()


