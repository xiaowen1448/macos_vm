import subprocess
def scp_plist(host, username,file_local_path,remote_file_path):
    """使用系统 ssh 命令测试 SSH 登录"""
    try:
        result = subprocess.run(
            ["scp","-o", "StrictHostKeyChecking=no",file_local_path,f"{username}@{host}:{remote_file_path}"],
            check=True
        )
        if result.returncode == 0:
            print(f"拷贝文件成功,拷贝命令如下:{result}")
            return True
        else:
            print(f"{result}++++++++++++++")
            return False
    except Exception as e:
        print(f"❌ 连接失败:")
    return False

'''
if __name__ == '__main__':
    host="192.168.119.156"
    username="wx"
    file_local_path="D:\\macos_vm\\plist\\chengpin\\config_1.plist"
    remote_file_path="/Volumes/EFI/CLOVER/config.plist"
    scp_plist(host,username,file_local_path,remote_file_path)
    print(f"------------")


'''
