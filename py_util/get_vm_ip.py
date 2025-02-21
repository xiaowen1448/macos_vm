import subprocess
import list_vm_files

vmrun="C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe"
def get_vm_ip(vm_path):
    try:
        # 调用 vmrun 获取虚拟机的 IP 地址
        command = f'"{vmrun}"  getGuestIPAddress {vm_path}'
        ip_address = subprocess.check_output(command, shell=True).decode().strip()

        if ip_address:
            return ip_address
        else:
            return "Unable to retrieve IP address."
    except subprocess.CalledProcessError as e:
        return f"Error executing vmrun: {e}"


if __name__ == "__main__":
    # 示例路径，替换为实际虚拟机文件路径
    directory = "D:\\macos_vm\\NewVM"  # 替换为你的目录路径
    vmx_files = list_vm_files.find_vmx_files(directory)
    # 输出所有找到的 .vmx 文件
    for vmx in vmx_files:
        print(f"Found VMX file: {vmx}")
        vm_path =vmx
        vm_ip = get_vm_ip(vm_path)
        print(f"VM IP Address: {vm_ip}")
