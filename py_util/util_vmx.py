import subprocess
import ipaddress
def find_vm_ip(vmrun,vm_path):
        try:
            command = f'"{vmrun}"  getGuestIPAddress {vm_path}'
            ip_address = subprocess.check_output(command, shell=True).decode().strip()
            ipaddress.ip_address(ip_address)
          #  print(f"获取虚拟机ip地址成功，")
            return ip_address
        except ValueError:
         #   print(f"未知的IP地址，虚拟机正在启动")
            return False




