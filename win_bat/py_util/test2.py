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
函数测试主要实现，判断执行auto_install.sh 后判断ip是否存活需要执行test2.py ，如存活代表脚本正在执行未完成，如不存活，代表脚本执行完毕
macos  开始重启部署步骤中，第二步骤需要执test.py 判断锁屏窗体是否获取，如未获取，则安装进程未完成，如获取，则安装进程已完成，可以执行登录。
test.py 为默认的没四秒执行一个for循环体，动态获取虚拟机macos的窗口体，直到全部列表虚拟机获取到，for循环执行结束
'''

def test2():
    # 示例路径，替换为实际虚拟机文件路径
    directory = "D:\\macos_vm\\NewVM"  # 替换为你的目录路径
    vmx_files = util_vmx.find_vmx_files(directory,".vmx")
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
                continue
            else:
                # 整个for循环未执行完毕，仍然错误，代表虚拟机无法获取ip，继续执行剩余for循环
                print(f"{inum}------------------------{for_len}")
                continue

test2()



