import util_vm
import util_vmx
import util_ssh
import util_cmd
import util_str
vmrun="C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe"
ssh_username="wx"
sh_name="~/CGSSessionScreenLockedTime.sh"
find_str="CGSSessionScreenLockedTime"
if __name__ == "__main__":
    # 示例路径，替换为实际虚拟机文件路径
    directory = "D:\\macos_vm\\NewVM"  # 替换为你的目录路径
    vmx_files = util_vm.find_vmx_files(directory)
    # 输出所有找到的 .vmx 文件
    for vmx in vmx_files:
        print(f"Found VMX file: {vmx}")
        vm_path =vmx
        vm_ip = util_vmx.find_vm_ip(vmrun,vm_path)
        print(f"VM IP Address: {vm_ip}")
        util_ssh.test_ssh_with_command(vm_ip, ssh_username)
        IOConsoleUsers=" ".join(util_cmd.execute_ssh_command(vm_ip,ssh_username,sh_name))
       # print(f"===================={IOConsoleUsers}")
        #print(type(IOConsoleUsers))
        str=util_str.contains_substring(IOConsoleUsers,find_str)
        #print(f"{str}===============")
        if str:
            print(f"匹配窗体时间戳成功，macos系统启动完毕可以登录")
        else:
            print(f"没有匹配到窗体时间戳，macos系统未成功启动，请等待！")