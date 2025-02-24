import util_vmx
import util_ip
import util_ssh
import util_cmd
import util_str
import time
import sys
vmrun="C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe"
ssh_username="wx"
sh_name_LockedTime="~/CGSSessionScreenLockedTime.sh"
#此参数用于匹配安装后的maco登录窗体，如匹配成功则代表macos启动成功
find_str_LockedTime="CGSSessionScreenLockedTime"
sh_name_finder="~/find_pgrep.sh"
#此参数用于匹配安装后的maco登录窗体，如匹配成功则代表macos启动成功
find_str_finder="finder"

'''
find_pgrep.sh 用于匹配成品虚拟机启动成功，用于匹配进程Finder，有进程代表系统启动完毕。,如下执行输出示例
PS D:\\macos_vm> ssh wx@192.168.119.156 '~/find_pgrep.sh'
330
PS D:\\macos_vm>
'''

def test():
    # 示例路径，替换为实际虚拟机文件路径
    directory = "D:\\macos_vm\\NewVM"  # 替换为你的目录路径
    vmx_files = util_vmx.find_vmx_files(directory)
    # 输出所有找到的 .vmx 文件
    for vmx in vmx_files:
        print(f"Found VMX file: {vmx}")
        vm_path =vmx
        vm_ip = util_ip.find_vm_ip(vmrun,vm_path)
        if vm_ip:
            print(f"获取虚拟机ip成功，开始尝试ssh登录")
            print(f"VM IP Address: {vm_ip}")
            util_ssh.test_ssh_with_command(vm_ip, ssh_username)
            if util_ssh:
                print(f"✅ SSH 登录成功：{ssh_username}@{vm_ip}")
                IOConsoleUsers = " ".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, sh_name_LockedTime))
                str = util_str.contains_substring(IOConsoleUsers, find_str_LockedTime)
                # print(f"{str}===============")
                if str:
                    print(f"匹配窗体时间戳成功，macos系统启动完毕可以登录")
                    # 此处为判断，重装后安装成功，匹配锁屏窗口
                    # 开始执行自动登录和禁用appleid提示
                    # ，注入五码脚本，重建nvrm，
                    sys.exit()
                else:
                    print(f"没有匹配到窗体时间戳，macos系统正在启动，请等待！")
                    # 此处为判断，执行安装脚本期间，匹配auto_install脚本进程，如存在则脚本正在执行，如ip不存活代表脚本执行成功，系统正在重启中
                    #匹配进程Finder，有进程代表系统启动完毕
                    IOConsoleUsers = " ".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, sh_name_finder))
                    str = util_str.contains_substring(IOConsoleUsers, find_str_finder)
                    print(f"{str}")
                    print(f"匹配到Finder进程，macos系统已经自动登录")
                    sys.exit()

            else:
                print(f"❌ SSH 登录失败：十秒后重新尝试")
                time.sleep(4)

        else:
            print(f"获取虚拟机ip失败，十秒后重新尝试获取，系统正在重启中")
            time.sleep(4)
            test()
test()



