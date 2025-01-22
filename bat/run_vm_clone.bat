@setlocal enabledelayedexpansion
@echo off
REM Set the template VM path
set BASE_DIR=%cd%
set TEMPLATE_PATH=%BASE_DIR%\..\TemplateVM\macos10.15
REM Set the storage path of the target VM
set VM_BASE_PATH=%BASE_DIR%\..\NewVM
set ISO_BASE_HOME=%BASE_DIR%\..\iso
set IP_PATH=%BASE_DIR%\ip
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
del  log\run.log
REM Perform batch creation
for /L %%i in (1,1,%VM_COUNT%) do (
    REM Create a new virtual machine directory
    set VM_DIR=%VM_BASE_PATH%\VM_%%i
	set /a sum=!sum!+%%i
    mkdir !VM_DIR!
    REM Copy the template VM file
	echo Start cloning the virtual machine files please wait   .......................
    xcopy /E /I %TEMPLATE_PATH% !VM_DIR!  >> log\run.log  2>&1
    echo  displayName = "macos10.15_%%i" >>  "!VM_DIR!\macos10.15.vmx"
	echo  sata0:0.fileName = "macos10.15_%%i.vmdk"  >>  "!VM_DIR!\macos10.15.vmx"
	echo  nvram = "macos10.15_%%i.nvram"  >>  "!VM_DIR!\macos10.15.vmx" 
	echo  extendedConfigFile = "macos10.15_%%i.vmxf" >> "!VM_DIR!\macos10.15.vmx" 
	echo sata0:1.fileName = "%ISO_BASE_HOME%\Installer_macOS_Catalina_10.15.7.iso"  >>  "!VM_DIR!\macos10.15.vmx" 
	echo  memsize="2048" >> "!VM_DIR!\macos10.15.vmx"
	move "!VM_DIR!\macos10.15.vmx" "!VM_DIR!\macos10.15_%%i.vmx"  >> log\run.log  2>&1
	move "!VM_DIR!\macos10.15.vmdk" "!VM_DIR!\macos10.15_%%i.vmdk"  >> log\run.log  2>&1
	move "!VM_DIR!\macos10.15.vmxf" "!VM_DIR!\macos10.15_%%i.vmxf" >> log\run.log  2>&1
	move "!VM_DIR!\macos10.15.nvram" "!VM_DIR!\macos10.15_%%i.nvram" >> log\run.log  2>&1
    echo Created VM_%%i at !VM_DIR!
	echo "Starting  launching virtual machines VM_%%i , please wait   ......................."
	%VMRUN_PATH%  start  !VM_DIR!\macos10.15_%%i.vmx 
	rem   nogui
)
echo All virtual machines have been created and are waiting to be started ...................  
echo The IP address is being scanned, please wait .................... 
echo  Obtaining the IP address of the VM is in progress!......................
rem :check
rem  goto check 
call get_vm_ip.bat
type %IP_PATH%\ip_list.txt
echo Start executing scripts in batches  ............................
rem  VM_COUNT  Number of virtual machines
rem  Set the number of config.plist to be used
for /f "tokens=* delims=" %%a in (%IP_PATH%\ip_list.txt) do (
	set /a plist_num+=1
	REM   ssh  -o StrictHostKeyChecking=no  cc@192.168.122.190  '/Users/wx/auto_install.sh'
	ssh  -o StrictHostKeyChecking=no  %ssh_uname%@%%a   '/Users/%ssh_uname%/mount_efi.sh'  >> log\run.log  2>&1
	scp %plist_path%\config_!plist_num!.plist  %ssh_uname%@%%a:/Volumes/EFI/CLOVER/config.plist  >> log\run.log  2>&1
	start cmd /k ssh  -o StrictHostKeyChecking=no  %ssh_uname%@%%a  '/Users/%ssh_uname%/auto_install.sh'
)
echo start revise kbjfrfpoJU ,Please wait  .................

pause
