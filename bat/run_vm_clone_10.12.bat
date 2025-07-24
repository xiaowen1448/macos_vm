@setlocal enabledelayedexpansion
@echo off
REM Set the template VM path
set BASE_DIR=%cd%
set TEMPLATE_PATH=%BASE_DIR%\..\TemplateVM\macos10.12
REM Set the storage path of the target VM
set VM_BASE_PATH=%BASE_DIR%\..\NewVM\10.12
set ISO_BASE_HOME=%BASE_DIR%\..\iso
set IP_PATH=%BASE_DIR%\var_files
set LOG_PATH=%BASE_DIR%\log
REM Set the number of virtual machines that need to be created
set VM_COUNT=2
set VMRUN_PATH=vmrun
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
copy /y nul %LOG_PATH%\run.log >> %LOG_PATH%\run.log  2>&1
REM Perform batch creation
set root_dir=%VM_BASE_PATH%
set "max_num=0"
for /d %%D in ("%root_dir%\VM_*") do (
    set "folder=%%~nxD"
    for /f "tokens=2 delims=_" %%A in ("!folder!") do (
        set /a "num=%%A"
        if !num! GTR !max_num! set "max_num=!num!"
    )
)
echo VM max folder is : VM_%max_num%
del %IP_PATH%\10.12_vmx_list.txt
for /L %%i in (1,1,%VM_COUNT%) do (
    REM Create a new virtual machine directory
	set /a "next_num=max_num+%%i"
    set VM_DIR=%VM_BASE_PATH%\VM_!next_num!
	rem set /a sum=!sum!+%%i
	rem  mkdir !VM_DIR!
    REM Copy the template VM file
	echo Start cloning the virtual machine files please wait   .......................
	vmrun -T ws clone  !TEMPLATE_PATH!\macos10.12.vmx  !VM_DIR!\macos10.12_VM_!next_num!.vmx  linked
	rem  使用sed 替换displayName 为虚拟机显示的名称
	sed -i "s/displayName = \".*\"/displayName = \"macos10.12_VM_!next_num!\"/"   !VM_DIR!\macos10.12_VM_!next_num!.vmx
	del sed*
    echo Created VM_!next_num! at !VM_DIR!
	echo "Starting  launching virtual machines VM_!next_num! , please wait   ......................."
	%VMRUN_PATH%  start  !VM_DIR!\macos10.12_VM_!next_num!.vmx 
	echo "!VM_DIR!\macos10.12_VM_!next_num!.vmx" >> %IP_PATH%\10.12_vmx_list.txt
	rem   nogui
)
echo All virtual machines have been created and are waiting to be started ...................  
echo The IP address is being scanned, please wait .................... 
echo  Obtaining the IP address of the VM is in progress!......................
rem :check
rem  goto check 
call 10.12_get_vm_ip.bat 10
type %IP_PATH%\10.12_ip_list.txt
echo "Started  launching virtual machines VM_!next_num! "
rem  VM_COUNT  Number of virtual machines
rem  Set the number of config.plist to be used

rem 执行安装后调用ip监控脚本test2.py
rem 如ip不存活代表虚拟机已经执行安装脚本完毕，则开始执行test.py
rem python ..\py_util\test2.py
python ..\py_util\test0.py
rem  执行重装后需要利用python判断远端auto_install进程是否存在和ip和ssh是否存活，ip消失后系统重启安装脚本则执行成功
