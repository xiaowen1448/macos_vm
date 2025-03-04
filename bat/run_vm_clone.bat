@setlocal enabledelayedexpansion
@echo off
REM Set the template VM path
set BASE_DIR=%cd%
set TEMPLATE_PATH=%BASE_DIR%\..\TemplateVM\macos10.15
REM Set the storage path of the target VM
set VM_BASE_PATH=%BASE_DIR%\..\NewVM
set ISO_BASE_HOME=%BASE_DIR%\..\iso
set IP_PATH=%BASE_DIR%\var_files
set LOG_PATH=%BASE_DIR%\log
REM Set the number of virtual machines that need to be created
set VM_COUNT=2
set VMRUN_PATH="C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"
set ssh_uname=wx
rem  Random numbers start
set sum=15
set num=1
rem set vmnet_ip=192.168.119.1
set nmap_count=253
rem  memory size 
set memsize="2048"
set plist_path=%BASE_DIR%\..\plist\chengpin
set plist_num=0

type %IP_PATH%\ip_list.txt
echo Start executing scripts in batches  ............................
rem  VM_COUNT  Number of virtual machines
rem  Set the number of config.plist to be used
for /f "tokens=* delims=" %%a in (%IP_PATH%\ip_list.txt) do (
	set /a plist_num+=1
	REM   ssh  -o StrictHostKeyChecking=no  cc@192.168.122.190  '/Users/wx/auto_install.sh'
	ssh  -o StrictHostKeyChecking=no  %ssh_uname%@%%a   '/Users/%ssh_uname%/mount_efi.sh'  >> %LOG_PATH%\run.log  2>&1
	scp %plist_path%\config_!plist_num!.plist  %ssh_uname%@%%a:/Volumes/EFI/CLOVER/config.plist  >> %LOG_PATH%\run.log  2>&1
	start cmd /k ssh  -o StrictHostKeyChecking=no  %ssh_uname%@%%a  '/Users/%ssh_uname%/auto_install.sh'
)
echo  Obtaining the IP address of the VM is in progress!......................
echo start revise kbjfrfpoJU ,Please wait  .................

rem 执行安装后调用ip监控脚本test2.py
rem 如ip不存活代表虚拟机已经执行安装脚本完毕，则开始执行test.py
rem python ..\py_util\test2.py
python ..\py_util\test.py
rem  执行重装后需要利用python判断远端auto_install进程是否存在和ip和ssh是否存活，ip消失后系统重启安装脚本则执行成功
