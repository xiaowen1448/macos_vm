from time import sleep
import util_vmx
import util_ip
import util_ssh
import util_cmd
import time
import util_vmx_ctrl
import shutil
import util_scp_plist
import re
import  json
import util_str
vmrun="C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe"
ssh_username="wx"
sh_user_home=f"/Users/{ssh_username}"
#此参数用于匹配安装后的maco登录窗体，如匹配成功则代表macos启动成功
str_LockedTime="CGSSessionScreenLockedTime"
str_finder=f"{sh_user_home}/find_pgrep.sh"
#此参数用于匹配安装后的maco登录窗体，如匹配成功则代表macos启动成功
str_CGSSessionScreenLockedTime=f"{sh_user_home}/CGSSessionScreenLockedTime.sh"
str_disable_appleAlert=f"{sh_user_home}/disable_appleAlert.sh"
str_dis_screensaver=f"{sh_user_home}/dis_screensaver.sh"
str_auto_send_vmkey=f"{sh_user_home}/auto_send_key.sh"
str_reboot=f"{sh_user_home}/reboot.sh"
str_mount_efi=f"{sh_user_home}/mount_efi.sh"
str_run_debug_sn=f"{sh_user_home}/run_debug_sn.sh"
str_run_debug_ju=f"{sh_user_home}/run_debug_ju.sh"
str_all_debug=f"{sh_user_home}/run_all_debug.sh"
str_run_debug_install=f"{sh_user_home}/find_startosinstall.sh"
str_auto_send_key=f"{sh_user_home}/auto_send_key.sh"
str_caff=f"{sh_user_home}/caff.sh"
remote_plist_dir="/Volumes/EFI/CLOVER/config.plist"
local_plist_dir=f"D:\\macos_vm\\plist\\chengpin\\"
temp_nvramfiles="D:\\macos_vm\\TemplateVM\\macos10.15\\macos10.15.nvram"
vm_directory = "D:\\macos_vm\\NewVM"  # 替换为你的目录路径
'''
find_pgrep.sh 用于匹配成品虚拟机启动成功，用于匹配进程Finder，有进程代表系统启动完毕。,如下执行输出示例
PS D:\\macos_vm> ssh wx@192.168.119.156 '~/find_pgrep.sh'
330
PS D:\\macos_vm>

执行安装脚本，直到ip不存活（代表安装脚本执行完毕），开始执行匹配窗体和finder进程
传入目录。，数组包含虚拟机名称和状态，返回True,则代表虚拟机关机，返回false代表虚拟机已开机

判断虚拟机是否存活，同时判断startosinstall进程是否存在，如存在则安装正在进行。
命令示例:ps aux | grep -i  startosinstall | grep -v grep
查找如果存在进程信息则为正在安装，如无或者ip不存活则代表成功
'''
def runos_install(vmx_file):
    vm_ip_true=False
    vm_ip = util_ip.find_vm_ip(vmrun, vmx_file)
    if vm_ip:
        sleep(4)
        print(f"获取虚拟机{vmx_file} ,脚本正在执行中")
        print(f"VM IP Address: {vm_ip}")
        return vm_ip_true
    else:
         print(f"获取虚拟机{vmx_file} ,脚本执行成功")
         sleep(4)
         vm_ip_true = True
         return vm_ip_true


#传入虚拟机参数，仅仅判断ip是否存活
def run_list_vmip(vmx_file):
    vm_ip = util_ip.find_vm_ip(vmrun, vmx_file)
    if vm_ip:
       # print(f"获取虚拟机{vmx_file} ip地址成功")
       # print(f"VM IP Address: {vm_ip}")
        return vm_ip
    else:
       # print(f"获取虚拟机{vmx_file} ip地址失败")
        return False

'''
获取目录下所有虚拟机的IP地址，返回数组，获取到则返回ip，失败则返回false
格式如下：
虚拟机获取IP,返回结果:{
    "data": {
        "macos10.15_1.vmx": "192.168.119.156",
        "macos10.15_2.vmx": "192.168.119.157"
    }
}


'''
def json_runlist_allvmips():
    data_vms={}
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    inum = 0
    for_len = len(vmx_files)
    if for_len==0:
        print(f"获取虚拟机文件失败，未找到虚拟机配置文件！")
    else:
        # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
        print(f"{vmx_files}")
        for vmx in vmx_files:
            vm_ip = run_list_vmip(vmx)
            str_vmx = vmx.split("\\")[-1]
            if run_list_vmip(vmx):
                #  print(f"虚拟机VM_{inum}获取ip成功")
                data_vms[str_vmx] = vm_ip

            else:
                #  print(f"虚拟机VM_{inum}获取ip失败")
                data_vms[str_vmx] = vm_ip
    data = {"data": data_vms}
    json_str = json.dumps(data, indent=4)
    print(f"虚拟机获取IP,返回结果:{json_str}")
    return json_str

#此函数用于发送唤醒 Mac 显示器，避免执行自动脚本返回失败。
def caff():
    data_vms = {}
    caff_ary=[]
    caff_flag=False
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    for_len = len(vmx_files)
    if for_len == 0:
        print(f"获取虚拟机文件失败，未找到虚拟机配置文件！")
    else:
        # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
        for vmx in vmx_files:
            str_vmx = vmx.split("\\")[-1]
            vm_ip = util_ip.find_vm_ip(vmrun, vmx)
            # 获取序列号信息
            str_debug = re.sub(r"\n", "","".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, str_caff)))
            data_vms[str_vmx] = str_debug
            caff_ary.append(str_debug)
        data = {"data": data_vms}
        json_str = json.dumps(data, indent=4)
        print(f"虚拟机执行唤醒显示器caff,返回结果:{caff_ary}")
        if all(item == "0" for item in caff_ary):
            caff_flag=True
            print(f"虚拟机执行唤醒显示器caff,执行成功")
        else:
            print(f"虚拟机执行唤醒显示器caff,执行失败")
        return caff_flag
#此函数用于发送虚拟机自动按键实现锁屏，解锁
def auto_send_keys():
    data_vms = {}
    keys_ary=[]
    keys_flag=False
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    for_len = len(vmx_files)
    if for_len == 0:
        print(f"获取虚拟机文件失败，未找到虚拟机配置文件！")
    else:

        # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
        for vmx in vmx_files:
            str_vmx = vmx.split("\\")[-1]
            vm_ip = util_ip.find_vm_ip(vmrun, vmx)
            # 获取序列号信息
            str_debug = re.sub(r"\n", "", "".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, str_auto_send_key)))
            data_vms[str_vmx] = str_debug
            keys_ary.append(str_debug)
        data = {"data": data_vms}
        json_str = json.dumps(data, indent=4)
        print(f"虚拟机执行auto_keys,返回结果:{keys_ary}")
        if all(item == "0" for item in keys_ary):
            print(f"虚拟机keys脚本执行成功")
            keys_flag=True
        else:
            print(f"虚拟机keys脚本执行失败")
        return keys_flag


#此函数用于发送脚本实现禁用appleid
#def dis_appleid():


'''

判断ssh登录是否成功,返回json串,成功返回true，失败返回空

'''
def  json_ssh_debug():
    data_vms = {}
    ssh_ary=[]
    ssh_flag=False
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    for_len = len(vmx_files)
    if for_len == 0:
        print(f"获取虚拟机文件失败，未找到虚拟机配置文件！")
    else:
        # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
        for vmx in vmx_files:
            vm_ip = util_ip.find_vm_ip(vmrun, vmx)
            ssh_str = util_ssh.test_ssh_with_command(vm_ip, ssh_username)
            data_vms[vmx.split("\\")[-1]] = ssh_str
            ssh_ary.append(ssh_str)
        data = {"data": data_vms}
        json_str = json.dumps(data, indent=4)
        print(f"虚拟机获取SSH登录,返回结果:{ssh_ary}")
        if all(item == True for item in ssh_ary):
            print(f"虚拟机ssh全部登录成功!")
            ssh_flag=True
        else:
            print(f"部分虚拟机ssh登录失败!")
            json_ssh_debug()
    return ssh_flag

#macos 获取所有虚拟机序列号json串
def json_sn_debug():
    data_vms = {}
    json_str = {}
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    for_len = len(vmx_files)
    if for_len == 0:
        print(f"获取虚拟机文件失败，未找到虚拟机配置文件！")
    else:

        # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
        for vmx in vmx_files:
            str_vmx = vmx.split("\\")[-1]
            vm_ip = util_ip.find_vm_ip(vmrun, vmx)
            #获取序列号信息
            str_debug = re.sub(r"\n", "", " ".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, str_run_debug_sn)))
            data_vms[str_vmx] = str_debug
        data = {"data": data_vms}
        json_str = json.dumps(data, indent=4)
        print(f"虚拟机获取SN信息,返回结果:{json_str}")
    return json_str
def json_all_debug():
    data_vms = {}
    json_str={}
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    for_len = len(vmx_files)
    if run_auto_lsit_vmip():
        print(f"全部虚拟机ip地址已经获取成功!")
        # ssh均登录成功,返回True
        if json_ssh_debug():
            if for_len == 0:
                print(f"获取虚拟机文件失败，未找到虚拟机配置文件！")
            else:

                # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
                for vmx in vmx_files:
                    str_vmx = vmx.split("\\")[-1]
                    vm_ip = util_ip.find_vm_ip(vmrun, vmx)
                    # 获取序列号信息
                    str_debug = re.sub(r"\n", "",
                                       " ".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, str_all_debug)))
                    data_vms[str_vmx] = str_debug
                data = {"data": data_vms}
                json_str = json.dumps(data, indent=4)
                print(f"虚拟机获取DEBUG信息,返回结果:{json_str}")
        else:
            json_all_debug()
    else:
        json_all_debug()
    return json_str

#macos 获取所有虚拟机JU值json串
def json_ju_debug():
    data_vms = {}
    json_str = {}
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    for_len = len(vmx_files)
    if for_len == 0:
        print(f"获取虚拟机文件失败，未找到虚拟机配置文件！")
    else:
        # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
        for vmx in vmx_files:
            str_vmx = vmx.split("\\")[-1]
            vm_ip = util_ip.find_vm_ip(vmrun, vmx)
            #获取序列号信息
            str_debug = re.sub(r"\n", ""," ".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, str_run_debug_ju)))
            data_vms[str_vmx] = str_debug
        data = {"data": data_vms}
        json_str = json.dumps(data, indent=4)
        print(f"虚拟机获取JU信息,返回结果:{json_str}")
    return json_str


def all_not_empty(arr):
    return all(arr)

#匹配finder进程，用户获取桌面登录
def json_finder_debug():
    data_vms = {}
    finder_ary=[]
    data_flag=False
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    for_len = len(vmx_files)
    # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
    if for_len == 0:
        print(f"获取虚拟机文件失败，未找到虚拟机配置文件！")
    else:
        for vmx in vmx_files:
            str_vmx = vmx.split("\\")[-1]
            vm_ip = util_ip.find_vm_ip(vmrun, vmx)
            # 获取序列号信息
            str_debug = "".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, str_finder)).replace("\n", "")
            data_vms[str_vmx] = str_debug
            finder_ary.append(str_debug)
       # data = {"data": data_vms}
       # json_str = json.dumps(data, indent=4)
        print(f"虚拟机获取Finder进程信息,返回结果:{finder_ary}")
        if all_not_empty(finder_ary):
            print(f"全部虚拟机获取Finder进程信息成功!")
            data_flag = True
        else:
            print(f"部分虚拟机获取Finder进程信息成功失败!")
            sleep(5)
            json_finder_debug()
        return data_flag
#匹配锁屏进程，用户获取桌面登录，返回匹配锁屏窗口，匹配成功则返回true，否则则返回false
def json_locker_debug():
    data_vms = {}
    locker_ary=[]
    locker_flag=False
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    for_len = len(vmx_files)
    # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
    if for_len == 0:
        print(f"获取虚拟机文件失败，未找到虚拟机配置文件！")
    else:
        for vmx in vmx_files:
            str_vmx = vmx.split("\\")[-1]
            vm_ip = util_ip.find_vm_ip(vmrun, vmx)
            # 获取序列号信息
            str_finder_ps= (" ".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, str_CGSSessionScreenLockedTime)))
                         #str.replace("\n", "")
            str_debug = util_str.contains_substring(str_finder_ps, str_LockedTime)
            data_vms[str_vmx] = str_debug
            locker_ary.append(str_debug)
        data = {"data": data_vms}
        json_str = json.dumps(data, indent=4)
        print(f"虚拟机获取CGSSessionScreenLockedTime进程信息,返回结果:{locker_ary}")
        if all(item == True for item in locker_ary):
            print(f"全部虚拟机获取LockedTime进程信息,返回结果:{locker_ary}")
            locker_flag=True
        else:
            print(f"部分虚拟机未获取LockedTime进程信息,返回结果:{locker_ary}")
            sleep(5)
            json_locker_debug()
    return locker_flag
#匹配自动安装进程，如匹配到正在安装，如无匹配或者无法联通则代表，安装成功正在重启
def json_installer_debug():
    data_vms = {}
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    for_len = len(vmx_files)
    if for_len == 0:
        print(f"获取虚拟机文件失败，未找到虚拟机配置文件！")
    else:
        # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
        for vmx in vmx_files:
            str_vmx = vmx.split("\\")[-1]
            vm_ip = util_ip.find_vm_ip(vmrun, vmx)
            # 获取序列号信息
            str_debug = "".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, str_run_debug_install)).replace("\n", "")
            data_vms[str_vmx] = str_debug
        data = {"data": data_vms}
        json_str = json.dumps(data, indent=4)
        print(f"虚拟机获取startinstall进程信息,返回结果:{json_str}")
        return json_str

#动态监控虚拟机IP地址和安装脚本进程，如脚本进程存在并且IP存活，则代表正在安装，否则则为执行完毕
def run_installer_status():
    data_ip = json_runlist_allvmips()
    data = json.loads(data_ip)
    data_installer=json_installer_debug()
    data2 = json.loads(data_installer)
    inum = 0
    inum2 = 0
    ip_ary=[]
    ins_ary=[]
    in_flag=False
    #检测虚拟机IP存活和进程存活同时为空或者同时为True
    len_str = len(data["data"].items())
    en_str = len(data2["data"].items())
    for key, value in data["data"].items():
        inum = inum + 1
        if value is False:
            print(f"虚拟机{key}获取ip地址失败")
            ip_ary.append(True)
        else:
            print(f"虚拟机{key}获取ip地址成功")
            ip_ary.append(False)
    for key2, value2 in data2["data"].items():
        inum2 = inum2 + 1
        if value2 == "":
            ins_ary.append(True)
            print(f"虚拟机{key2}获取installer进程失败")
        else:
            print(f"虚拟机{key2}获取installer进程成功")
            ins_ary.append(False)
    print(ip_ary)
    print(ins_ary)
    if  all(item == True for item in ip_ary) and   all(item == True for item in ins_ary):
        print(f"所有虚拟机脚本执行完毕正在重启！")
        in_flag = True
    else:
        print(f"部分虚拟机未执行完毕！请等待")
        sleep(5)
        return False
    print(f"{in_flag}+++++++++++++++++++++++++++")
    return in_flag


#动态监控虚拟机ip是否存活，五秒后重新尝试，
def run_auto_lsit_vmip():
    data_ip = json_runlist_allvmips()
    data = json.loads(data_ip)
    inum=0
    ip_flag=False
    len_str=len(data["data"].items())
    for key, value in data["data"].items():
        inum = inum + 1
        #print(f"虚拟机{key},ip地址:{value}")
        if value:
            if inum < len_str:
                print(f"虚拟机{key},ip地址:{value}获取成功")
                continue
            else:
                print(f"虚拟机{key},ip地址:{value}获取成功")
                ip_flag=True
        else:
            if inum<len_str:
                print(f"虚拟机{key},ip地址:{value},获取失败！,五秒钟后重新尝试获取....")
                continue
            else:
                sleep(5)
                print(f"虚拟机{key},ip地址:{value},获取失败！,五秒钟后重新尝试获取....")
                run_auto_lsit_vmip()
    return ip_flag

def  dis_appleid():
    data_vms = {}
    finder_ary = []
    data_flag = False
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    for_len = len(vmx_files)
    # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
    if for_len == 0:
        print(f"获取虚拟机文件失败，未找到虚拟机配置文件！")
    else:
        for vmx in vmx_files:
            str_vmx = vmx.split("\\")[-1]
            vm_ip = util_ip.find_vm_ip(vmrun, vmx)
            # 获取序列号信息
            str_debug = "".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, str_disable_appleAlert)).replace("\n", "")
            data_vms[str_vmx] = str_debug
            finder_ary.append(str_debug)
        # data = {"data": data_vms}
        # json_str = json.dumps(data, indent=4)
        print(f"虚拟机执行str_disable_appleAlert,返回结果:{finder_ary}")
        if all_not_empty(finder_ary):
            print(f"全部虚拟机执行str_disable_appleAlert)成功!")
            data_flag = True
        else:
            print(f"虚拟机str_disable_appleAlert)失败!")
    return data_flag

#禁用屏幕锁定
def dis_screensaver():
    data_vms = {}
    finder_ary = []
    data_flag = False
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    for_len = len(vmx_files)
    # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
    if for_len == 0:
        print(f"获取虚拟机文件失败，未找到虚拟机配置文件！")
    else:
        for vmx in vmx_files:
            str_vmx = vmx.split("\\")[-1]
            vm_ip = util_ip.find_vm_ip(vmrun, vmx)
            # 获取脚本输出
            str_debug = "".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, str_dis_screensaver)).replace("\n","")
            data_vms[str_vmx] = str_debug
            finder_ary.append(str_debug)
        # data = {"data": data_vms}
        # json_str = json.dumps(data, indent=4)
        print(f"虚拟机执行脚本str_dis_screensaver,返回结果:{finder_ary}")
        if all_not_empty(finder_ary):
            print(f"全部虚拟机执行脚本str_dis_screensaver成功!")
            data_flag = True
        else:
            print(f"全部虚拟机执行脚本str_dis_screensaver)失败!")
    return data_flag


def scp_plist():
    data_vms = {}
    plist_ary = []
    data_flag = False
    inum=0
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    for_len = len(vmx_files)
    # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
    if for_len == 0:
        print(f"获取虚拟机文件失败，未找到虚拟机配置文件！")
    else:
        for vmx in vmx_files:
            inum=inum+1
            str_vmx = vmx.split("\\")[-1]
            vm_ip = util_ip.find_vm_ip(vmrun, vmx)
            util_cmd.execute_ssh_command(vm_ip, ssh_username, str_mount_efi)
            file_local_path = f"{local_plist_dir}config_{inum}.plist"
            plist_flag=util_scp_plist.scp_plist(vm_ip, ssh_username, file_local_path, remote_plist_dir)
        # data = {"data": data_vms}
        # json_str = json.dumps(data, indent=4)
            plist_ary.append(plist_flag)
        print(f"虚拟机执行拷贝plist文件,返回结果:{plist_ary}")
        if all(item == True for item in plist_ary):
            print(f"所有虚拟机执行拷贝plist文件成功!")
            data_flag = True
        else:
            print(f"虚虚拟机执行拷贝plist文件失败!")
    return  data_flag

def run00():
    f_string_array = []#安装完毕的数组，和为安装完毕的数组
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    inum = 0
    for_len = len(vmx_files)
    # 输出所有找到的 .vmx 文件vmx_files = util_vmx.find_vmx_files(directory,".vmx")
    for vmx in vmx_files:
        if runos_install(vmx):
            print(f"虚拟机{vmx}安装脚本执行完毕开始进行下一步...........")
            f_string_array.extend([True])
        else:
            print(f"虚拟机{vmx}安装脚本正在执行请稍等...........")
            f_string_array.extend([False])
    print(f"虚拟机vmx，正在执行脚本安装,返回结果:{f_string_array}")
    return  f_string_array


def run03():
    #列出虚拟机ip
    data_ip=json_runlist_allvmips()
    #列出ssh登录返回值
    json_ssh_debug()
    #列出序列号
    json_sn_debug()
    #列出ju值
    json_ju_debug()
    #列出finder进程信息
    json_finder_debug()

    #匹配autoinstall进程
    json_installer_debug()
    #判断数组值是否相同
    #
   # data=json.loads(data_ip)
    run_auto_lsit_vmip()

def rebuild_nvram():
    vmx_files = util_vmx.find_vmx_files(vm_directory, ".vmx")
    for vmx in vmx_files:
        print(f"Found VMX file: {vmx}")
        vm_path = vmx
      # vm_ip = util_ip.find_vm_ip(vmrun, vm_path)
        print(f"nvram文件：{vm_path.replace("vmx", "nvram")}")
        util_vmx_ctrl.ctrl_vm(vmrun, "stop", vm_path)
        print(f"虚拟机{vm_path}已经停止!")
        shutil.copy(temp_nvramfiles, vm_path.replace("vmx", "nvram"))
        print(f"虚拟机{vm_path}nvram已经重建")
        util_vmx_ctrl.ctrl_vm(vmrun, "start", vm_path)
        print(f"虚拟机{vm_path}已经启动!")
def test():
    # 示例路径，替换为实际虚拟机文件路径
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
                      直接将提前编辑好的nvram文件复制到每台虚拟机即可，复制期间防止文件被占用，需要将虚拟机停机，拷贝后，再次开机。
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
                    if for_len == inum:
                        # 整个for循环执行完毕，仍然错误，代表虚拟机无法获取ip，整个for循环全部重新执行
                        print(f"{inum}++++++++++++++++++++++++++++++{for_len}")
                        test()
                    else:
                        # 整个for循环未执行完毕，仍然错误，代表虚拟机无法获取ip，继续执行剩余for循环
                        print(f"{inum}&&&&&&&&&&&&&&&&&&&&&&&&&{for_len}")
                        continue
                else:

                    print(f"没有匹配到窗体时间戳，虚拟机{vmx}系统正在启动，请等待！")
                    str_finder_ps = util_str.contains_substring(
                        " ".join(util_cmd.execute_ssh_command(vm_ip, ssh_username, str_finder)), str_finder)
                    print(f"{str_finder_ps}")
                    print(f"匹配到Finder进程，虚拟机{vmx}系统正在安装配置!")

            else:
                print(f"❌ 虚拟机{vmx}系统 SSH 登录失败：十秒后重新尝试")
                time.sleep(4)
                if for_len == inum:
                    # 整个for循环执行完毕，仍然错误，代表虚拟机无法获取ip，整个for循环全部重新执行
                    print(f"{inum}!!!!!!!!!!!!!!!!!!!!!!!!!!!{for_len}")
                    test()
                else:
                    # 整个for循环未执行完毕，仍然错误，代表虚拟机无法获取ip，继续执行剩余for循环
                    print(f"{inum}@@@@@@@@@@@@@@@@@@@@@@@@@@@@{for_len}")
                    continue
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

def run04():
    #脚本函数只运行一次，用于判断auto安装脚本是否执行完毕
    in_flag=run_installer_status()
    print(f"auto安装脚本:{in_flag}=========================")
    if in_flag:
        run05()
    else:
        print(f"auto安装脚本:{in_flag}------------------------------")
        run04()
def  run05():
    if run_auto_lsit_vmip():
        print(f"全部虚拟机ip地址已经获取成功!")
        # ssh均登录成功,返回True
        if json_ssh_debug():
            if json_locker_debug():
                # 获取所有虚拟机的锁屏状态匹配，全部匹配则为True，此状态为安装完毕后，ju更改成功的状态
                #print(json_locker_debug())
                # 开始执行唤醒脚本和自动key脚本
                caff()
                auto_send_keys()
                # 开始执行disabled appleid 脚本
                dis_appleid()
                #执行禁用屏幕锁定脚本
                dis_screensaver()
                # 执行scp plist文件，如果不存在plist，则执行脚本生成
               # subprocess.run(["D:\\macos_vm\\bat\\disable_appleAlert.bat"], shell=True)
                # 激活黑屏的mac，开始发送自动按键
                caff()
                auto_send_keys()
               # subprocess.run(["D:\\macos_vm\\bat\\scp_plist.bat"], shell=True)
                #拷贝五码plist文件
                scp_plist()
                #subprocess.run(["D:\\macos_vm\\bat\\rebuild_nvram.bat"], shell=True)
                #重建nvram文件
                rebuild_nvram()
                print(f"所有虚拟机均已经配置完毕,等待重启中................")
                json_all_debug()
            else:
                run05()
        else:
            run05()
    else:
        run05()

run04()