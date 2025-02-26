import subprocess

def ctrl_vm(vmrun,vm_ctrl,vm_path):
        try:
            command = f'"{vmrun}"  {vm_ctrl}  {vm_path} nogui'
            print(f"{command}")
            str_output = subprocess.check_output(command, shell=True).decode().strip()
            print(f"虚拟机已经{vm_ctrl}......")
        except Exception as e :
            print("f{e}")
            return False


if __name__ == '__main__':
   vmrun="C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe"
   vm_path="D:\\macos_vm\\NewVM\\VM_1\\macos10.15_1.vmx"
   vm_ctrl="stop"
   ctrl_vm(vmrun,vm_ctrl,vm_path)