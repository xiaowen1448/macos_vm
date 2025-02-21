import util_vm
import util_vmx
vmrun="C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe"
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