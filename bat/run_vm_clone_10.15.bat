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
del %IP_PATH%\10.15_vmx_list.txt
for /L %%i in (1,1,%VM_COUNT%) do (
    REM Create a new virtual machine directory
	set /a "next_num=max_num+%%i"
    set VM_DIR=%VM_BASE_PATH%\VM_!next_num!
	rem set /a sum=!sum!+%%i
    mkdir !VM_DIR!
    REM Copy the template VM file
	echo Start cloning the virtual machine files please wait   .......................
    xcopy /E /I %TEMPLATE_PATH% !VM_DIR!  >> %LOG_PATH%\run.log  2>&1
    echo displayName = "macos10.15_!next_num!" >>  "!VM_DIR!\macos10.15.vmx"
	echo sata0:0.fileName = "macos10.15_!next_num!.vmdk"  >>  "!VM_DIR!\macos10.15.vmx"
	echo nvram = "macos10.15_!next_num!.nvram"  >>  "!VM_DIR!\macos10.15.vmx" 
	echo extendedConfigFile = "macos10.15_!next_num!.vmxf" >> "!VM_DIR!\macos10.15.vmx" 
	echo sata0:1.fileName = "%ISO_BASE_HOME%\Installer_macOS_Catalina_10.15.7.iso"  >>  "!VM_DIR!\macos10.15.vmx" 
	echo memsize="2048" >> "!VM_DIR!\macos10.15.vmx"
	move "!VM_DIR!\macos10.15.vmx" "!VM_DIR!\macos10.15_!next_num!.vmx"  >> %LOG_PATH%\run.log  2>&1
	move "!VM_DIR!\macos10.15.vmdk" "!VM_DIR!\macos10.15_!next_num!.vmdk"  >> %LOG_PATH%\run.log  2>&1
	move "!VM_DIR!\macos10.15.vmxf" "!VM_DIR!\macos10.15_!next_num!.vmxf" >> %LOG_PATH%\run.log  2>&1
	move "!VM_DIR!\macos10.15.nvram" "!VM_DIR!\macos10.15_!next_num!.nvram" >> %LOG_PATH%\run.log  2>&1
    echo Created VM_!next_num! at !VM_DIR!
	echo "Starting  launching virtual machines VM_!next_num! , please wait   ......................."
	%VMRUN_PATH%  start  !VM_DIR!\macos10.15_!next_num!.vmx 
	echo "!VM_DIR!\macos10.15_!next_num!.vmx" >> %IP_PATH%\10.15_vmx_list.txt
	rem   nogui
)
echo All virtual machines have been created and are waiting to be started ...................  
echo The IP address is being scanned, please wait .................... 
echo  Obtaining the IP address of the VM is in progress!......................
rem :check
rem  goto check 
call get_vm_ip.bat 30
type %IP_PATH%\10.15_ip_list.txt
echo Start executing scripts in batches  ............................
rem  VM_COUNT  Number of virtual machines
rem  Set the number of config.plist to be used
for /f "tokens=* delims=" %%a in (%IP_PATH%\10.15_ip_list.txt) do (
	set /a plist_num+=1
	REM   ssh  -o StrictHostKeyChecking=no  cc@192.168.122.190  '/Users/wx/auto_install.sh'
	rem  ssh  -o StrictHostKeyChecking=no  %ssh_uname%@%%a   '/Users/%ssh_uname%/mount_efi.sh'  >> %LOG_PATH%\run.log  2>&1
	rem scp %plist_path%\config_!plist_num!.plist  %ssh_uname%@%%a:/Volumes/EFI/CLOVER/config.plist  >> %LOG_PATH%\run.log  2>&1
	start cmd /k ssh  -o StrictHostKeyChecking=no  %ssh_uname%@%%a  '/Users/%ssh_uname%/auto_install.sh'
)
echo  Obtaining the IP address of the VM is in progress!......................
echo start revise kbjfrfpoJU ,Please wait  .................

rem 执行安装后调用ip监控脚本test2.py
rem 如ip不存活代表虚拟机已经执行安装脚本完毕，则开始执行test.py
rem python ..\py_util\test2.py
python ..\py_util\test.py
rem  执行重装后需要利用python判断远端auto_install进程是否存在和ip和ssh是否存活，ip消失后系统重启安装脚本则执行成功
