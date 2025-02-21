import subprocess


def find_vm_ip(vmrun,vm_path):
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



