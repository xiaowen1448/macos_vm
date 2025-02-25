import util_vmx
import util_ip
import util_ssh
import util_cmd
import util_str
import time
import util_vmx_ctrl
import shutil
import util_scp_plist
vmrun="C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe"
ssh_username="wx"
str_CGSSessionScreenLockedTime="~/CGSSessionScreenLockedTime.sh"
#此参数用于匹配安装后的maco登录窗体，如匹配成功则代表macos启动成功
str_LockedTime="CGSSessionScreenLockedTime"
sh_name_finder="~/find_pgrep.sh"
#此参数用于匹配安装后的maco登录窗体，如匹配成功则代表macos启动成功
str_finder="finder"
str_disable_appleAlert="~/disable_appleAlert.sh"
str_auto_send_vmkey="~/auto_send_key.sh"
str_reboot="~/reboot.sh"
str_mount_efi="~/mount_efi.sh"
remote_plist_dir="/Volumes/EFI/CLOVER/config.plist"
local_plist_dir="D:\\macos_vm\\plist\\chengpin\\config_1.plist"
temp_nvramfiles="D:\\macos_vm\\TemplateVM\\macos10.15\\macos10.15.nvram"
'''

find_pgrep.sh 用于匹配成品虚拟机启动成功，用于匹配进程Finder，有进程代表系统启动完毕。,如下执行输出示例
PS D:\\macos_vm> ssh wx@192.168.119.156 '~/find_pgrep.sh'
330
PS D:\\macos_vm>
'''

def test():
    # 示例路径，替换为实际虚拟机文件路径
    vm_directory = "D:\\macos_vm\\NewVM"  # 替换为你的目录路径
    vmx_files = util_vmx.find_vmx_files(vm_directory,".vmx")
    inum = 0
    for_len=len(vmx_files)
    # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
    for vmx in vmx_files:
        print(f"Found VMX file: {vmx}")
        inum=inum+1
        vm_path = vmx
        vm_ip = util_ip.find_vm_ip(vmrun, vm_path)
        if vm_ip:
            print(f"获取虚拟机{vmx} ip地址成功，开始尝试ssh登录")
            print(f"VM IP Address: {vm_ip}")
            util_ssh.test_ssh_with_command(vm_ip, ssh_username)
            if util_ssh:
                print(f"✅ SSH 登录成功：{ssh_username}@{vm_ip}")
                IOConsoleUsers = " ".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, str_CGSSessionScreenLockedTime))
                str = util_str.contains_substring(IOConsoleUsers, str_LockedTime)
                # print(f"{str}===============")
                if str:
                    print(f"匹配窗体时间戳成功，虚拟机{vmx}系统启动完毕可以登录")
                    # 此处为判断，重装后安装成功，匹配锁屏窗口
                    # 开始执行自动登录和禁用appleid提示
                    # ，注入五码脚本，重建nvrm，
                    # sys.exit()
                    #开始执行禁用disabled appledid 脚本，
                    util_cmd.execute_ssh_command(vm_ip, ssh_username, str_auto_send_vmkey)
                    #subprocess.run(r'D:\\macos_vm\\bat\\disable_appleAlert.bat', shell=True)
                    util_cmd.execute_ssh_command(vm_ip, ssh_username, str_disable_appleAlert)
                   # subprocess.run(r'D:\\macos_vm\\bat\\rebuild_nvram.bat', shell=True)
                    #util_cmd.execute_ssh_command(vm_ip, ssh_username, str_reboot)
                    #执行efi分区挂载脚本
                    util_cmd.execute_ssh_command(vm_ip, ssh_username, str_mount_efi)
                    # 打印脚本输出
                    #print(f"虚拟机{vmx}脚本执行完毕，系统已经重启，ju值，自动登录，appleid提示已完成配置!")
                    #拷贝五码文件，循环遍历plist文件vmx_files = util_vmx.find_vmx_files(directory,".plist")
                    file_local_path = f"D:\\macos_vm\\plist\\chengpin\\config_{inum}.plist"
                    print(f"{file_local_path}=======================")
                    remote_file_path = "/Volumes/EFI/CLOVER/config.plist"
                    util_scp_plist.scp_plist(vm_ip, ssh_username, local_plist_dir, remote_plist_dir)
                    #停止虚拟机\
                    print(f"{vm_path.replace("vmx","nvram")}")
                    util_vmx_ctrl.ctrl_vm(vmrun,"stop",vm_path)
                    #重建nvram 循环遍历nvram文件
                    shutil.copy(temp_nvramfiles, vm_path.replace("vmx","nvram"))
                    print(f"虚拟机{vm_path}nvram已经重建")
                    #启动虚拟机
                    util_vmx_ctrl.ctrl_vm(vmrun, "start", vm_path)
                    print(f"虚拟机{vm_path}已经启动!")
                    #print(result2.stdout)
                    continue
                else:
                    print(f"没有匹配到窗体时间戳，虚拟机{vmx}系统正在启动，请等待！")
                    # 此处为判断，执行安装脚本期间，匹配auto_install脚本进程，如存在则脚本正在执行，如ip不存活代表脚本执行成功，系统正在重启中
                    # 匹配进程Finder，有进程代表系统启动完毕
                    IOConsoleUsers = " ".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, sh_name_finder))
                    str = util_str.contains_substring(IOConsoleUsers, str_finder)
                    print(f"{str}")
                    print(f"匹配到Finder进程，虚拟机{vmx}系统正在安装配置!")
                    time.sleep(4)
                    if for_len == inum:
                        # 整个for循环执行完毕，仍然错误，代表虚拟机无法获取ip，整个for循环全部重新执行
                        print(f"{inum}====================={for_len}")
                        test()
                    else:
                        # 整个for循环未执行完毕，仍然错误，代表虚拟机无法获取ip，继续执行剩余for循环
                        print(f"{inum}------------------------{for_len}")
                        continue

            else:
                print(f"❌ 虚拟机{vmx}系统 SSH 登录失败：十秒后重新尝试")
                time.sleep(4)
                test()

        else:
            print(f"获取虚拟机{vmx} ip地址失败，十秒后重新尝试获取，系统正在重启中")
            time.sleep(4)
            if for_len==inum:
                #整个for循环执行完毕，仍然错误，代表虚拟机无法获取ip，整个for循环全部重新执行
                print(f"{inum}====================={for_len}")
                test()
            else:
                # 整个for循环未执行完毕，仍然错误，代表虚拟机无法获取ip，继续执行剩余for循环
                print(f"{inum}------------------------{for_len}")
                continue

test()



