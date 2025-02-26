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
plist_num=1
remote_plist_dir="/Volumes/EFI/CLOVER/config.plist"
local_plist_dir=f"D:\\macos_vm\\plist\\chengpin\\config_{plist_num}.plist"
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
                str_finder_ps = util_str.contains_substring(IOConsoleUsers, str_LockedTime)
                # print(f"{str}===============")
                if str_finder_ps:
                    print(f"匹配窗体时间戳成功，虚拟机{vmx}系统启动完毕可以登录")
                    '''
                    1.此处为判断，重装后安装成功，匹配锁屏窗口
                    2.开始执行自动登录和禁用appleid提示，开始执行禁用disabled appledid 脚本，
                    3.执行挂在efi分区，注入五码脚本，重建nvrm，
                    4.讲提前生成的五码plist成品配置文件，使用scp拷贝到远端目录。
                    5.由于重新安装macos后，引导顺序会更改，需要将clover设置为第一引导，
                      直接将提前编辑好的nvram文件复制到每台虚拟机即可，复制旗舰防止文件被占用，需要将虚拟机停机，拷贝后，再次开机。
                    '''
                    util_cmd.execute_ssh_command(vm_ip, ssh_username, str_auto_send_vmkey)
                    util_cmd.execute_ssh_command(vm_ip, ssh_username, str_disable_appleAlert)
                    util_cmd.execute_ssh_command(vm_ip, ssh_username, str_mount_efi)
                    file_local_path = f"D:\\macos_vm\\plist\\chengpin\\config_{inum}.plist"
                    util_scp_plist.scp_plist(vm_ip, ssh_username, file_local_path, remote_plist_dir)
                    print(f"nvram文件：{vm_path.replace("vmx","nvram")}")
                    util_vmx_ctrl.ctrl_vm(vmrun,"stop",vm_path)
                    print(f"虚拟机{vm_path}已经停止!")
                    shutil.copy(temp_nvramfiles, vm_path.replace("vmx","nvram"))
                    print(f"虚拟机{vm_path}nvram已经重建")
                    util_vmx_ctrl.ctrl_vm(vmrun, "start", vm_path)
                    print(f"虚拟机{vm_path}已经启动!")
                    continue
                else:
                    '''
                    此处判断为获取finder进程，系统为启动状态，或者是启动后配置状态，无锁屏，代表未配置完成，或者是系统启动后，自动登录已完成
                    '''
                    print(f"没有匹配到窗体时间戳，虚拟机{vmx}系统正在启动，请等待！")
                    str_finder_ps = util_str.contains_substring(" ".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, sh_name_finder)), str_finder)
                    print(f"{str_finder_ps}")
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



