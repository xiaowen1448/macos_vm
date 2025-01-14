@setlocal enabledelayedexpansion
@echo off
REM Set the template VM path
set TEMPLATE_PATH=D:\macos_vm\TemplateVM\macos10.15
REM Set the storage path of the target VM
set VM_BASE_PATH=D:\macos_vm\NewVM
REM Set the number of virtual machines that need to be created
set VM_COUNT=2
rem  Random numbers start
set sum=15
set num=1
set vmnet_ip=192.168.119.1
REM Perform batch creation
for /L %%i in (1,1,%VM_COUNT%) do (

    REM Create a new virtual machine directory
    set VM_DIR=%VM_BASE_PATH%\VM_%%i
	set /a sum=!sum!+%%i
    mkdir !VM_DIR!
    REM Copy the template VM file
    xcopy /E /I %TEMPLATE_PATH% !VM_DIR! >nul
    echo  displayName = "macos10.15_%%i" >>  "!VM_DIR!\macos10.15.vmx"
	echo  sata0:0.fileName = "macos10.15_%%i.vmdk"  >>  "!VM_DIR!\macos10.15.vmx"
	echo  nvram = "macos10.15_%%i.nvram"  >>  "!VM_DIR!\macos10.15.vmx" 
	echo  extendedConfigFile = "macos10.15_%%i.vmxf"   >>  "!VM_DIR!\macos10.15.vmx" 
	REM nvram = "macOS 10.15.nvram"  bios  
	REM displayName = "macOS 10.15"
	REM sata0:0.fileName = "macOS 10.15.vmdk"
	REM extendedConfigFile = "macOS 10.15.vmxf"
	move "!VM_DIR!\macos10.15.vmx"  "!VM_DIR!\macos10.15_%%i.vmx"
	move  "!VM_DIR!\macos10.15.vmdk"    "!VM_DIR!\macos10.15_%%i.vmdk" 
	move  "!VM_DIR!\macos10.15.vmxf"    "!VM_DIR!\macos10.15_%%i.vmxf"
	move  "!VM_DIR!\macos10.15.nvram"    "!VM_DIR!\macos10.15_%%i.nvram"
    echo Created VM %%i at !VM_DIR!
	echo  "Start launching virtual machines in bulk, please wait   ......................."
	"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"    start  !VM_DIR!\macos10.15_%%i.vmx
)
echo "All virtual machines have been created and are waiting to be started ..................."
rem   the virtual machine to starting   please wait    .................... 
timeout /t 240 
echo  "The IP address is being scanned, please wait    ...................."
REM  Define the range of nmap scan addresses  for Example   192.168.119.2-10
for /f "tokens=1,2,3,4 delims=." %%a in ("%vmnet_ip%") do (
	set /a result_d=%%d + %num%
	set new_vmnet_ip=%%a.%%b.%%c.!result_d!
)
nmap !new_vmnet_ip!-%VM_COUNT%  > example.txt 
awk -F: "/report/{ print $0 }" example.txt  | awk -F" " "{ print $NF }"  | awk -F"(" "{ print $2 }"  | awk -F")" "{ print $1 }"  > ip_list.txt
echo  "IP address information is saved in this text  ip_list.txt"
echo  "ip address  is done   ...................."
echo  " run  ssh  going  ............................"
for /f "tokens=* delims=" %%a in (ip_list.txt) do (
	REM   ssh  -o StrictHostKeyChecking=no  cc@192.168.122.190  '/Users/wx/auto_install.sh'
	  start cmd /k ssh  -o StrictHostKeyChecking=no  wx@%%a  '/Users/wx/auto_install.sh'
)
echo   "start revise   JU ,Please wait  ................."

pause
