import util_vmx
import util_ip
import time
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

def test2():
    # 示例路径，替换为实际虚拟机文件路径
    directory = "D:\\macos_vm\\NewVM"  # 替换为你的目录路径
    vmx_files = util_vmx.find_vmx_files(directory)
    # 输出所有找到的 .vmx 文件
    inum = 0
    for_len = len(vmx_files)
    for vmx in vmx_files:
        print(f"Found VMX file: {vmx}")
        vm_path = vmx
        inum = inum + 1
        vm_ip = util_ip.find_vm_ip(vmrun, vm_path)
        if vm_ip:
            print(f"获取虚拟机{vmx} ip地址存活中!安装进程正在执行")
            print(f"VM IP Address: {vm_ip}")
            if for_len == inum:
                # 整个for循环执行完毕，仍然错误，代表虚拟机无法获取ip，整个for循环全部重新执行
                print(f"{inum}====================={for_len}")
                test2()
            else:
                time.sleep(4)
                # 整个for循环未执行完毕，仍然错误，代表虚拟机无法获取ip，继续执行剩余for循环
                print(f"{inum}------------------------{for_len}")
                continue
        else:
            print(f"虚拟机{vmx}ip地址无法获取,安装脚本执行成功，系统正在重启中")
            time.sleep(4)
            if for_len == inum:
                # 整个for循环执行完毕，仍然错误，代表虚拟机无法获取ip，整个for循环全部重新执行
                print(f"{inum}====================={for_len}")
                test2()
            else:
                # 整个for循环未执行完毕，仍然错误，代表虚拟机无法获取ip，继续执行剩余for循环
                print(f"{inum}------------------------{for_len}")
                continue
test2()



