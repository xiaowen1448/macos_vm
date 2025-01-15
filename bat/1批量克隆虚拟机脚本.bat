@setlocal enabledelayedexpansion
@echo off
REM Set the template VM path
set TEMPLATE_PATH=D:\macos_vm\TemplateVM\macos10.15
REM Set the storage path of the target VM
set VM_BASE_PATH=D:\macos_vm\NewVM
REM Set the number of virtual machines that need to be created
set VM_COUNT=4
rem  Random numbers start
set sum=15
set num=1
set vmnet_ip=192.168.119.1
set nmap_count=253
rem  memory size 
set memsize="2048"
set plist_path=D:\macos_vm\plist\chengpin
set plist_num=0
echo  "" > run.log
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
	echo  memsize="2048"  >>   "!VM_DIR!\macos10.15.vmx"
	REM nvram = "macOS 10.15.nvram"  bios  
	REM displayName = "macOS 10.15"
	REM sata0:0.fileName = "macOS 10.15.vmdk"
	REM extendedConfigFile = "macOS 10.15.vmxf"
	move "!VM_DIR!\macos10.15.vmx"  "!VM_DIR!\macos10.15_%%i.vmx"  >> run.log  2>&1
	move  "!VM_DIR!\macos10.15.vmdk"    "!VM_DIR!\macos10.15_%%i.vmdk"  >> run.log  2>&1
	move  "!VM_DIR!\macos10.15.vmxf"    "!VM_DIR!\macos10.15_%%i.vmxf" >> run.log  2>&1
	move  "!VM_DIR!\macos10.15.nvram"    "!VM_DIR!\macos10.15_%%i.nvram" >> run.log  2>&1
    echo Created VM_%%i at !VM_DIR!
	echo "Starting  launching virtual machines VM_%%i , please wait   ......................."
	"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"    start  !VM_DIR!\macos10.15_%%i.vmx
)
echo All virtual machines have been created and are waiting to be started ................... 
rem   the virtual machine to starting   please wait    .................... 
rem   Wait for the VM to start up and obtain the IP address of the VM
timeout /t 240 
echo The IP address is being scanned, please wait    .................... 
REM  Define the range of nmap scan addresses  for Example   192.168.119.2-10
for /f "tokens=1,2,3,4 delims=." %%a in ("%vmnet_ip%") do (
	set /a result_d=%%d + %num%
	set new_vmnet_ip=%%a.%%b.%%c.!result_d!
)
echo !new_vmnet_ip!-%nmap_count%
nmap !new_vmnet_ip!-%nmap_count%  > example.txt 
awk -F: "/report/{ print $0 }" example.txt | awk -F" " "{ print $NF }"  > ip_list.txt  
sed -i  "s/(//g"  ip_list.txt 
sed -i  "s/)//g"  ip_list.txt
del sed*
rem  echo  "IP address information is saved in this text  ip_list.txt"
echo nmap ip address  is done   ....................
echo Start executing scripts in batches  ............................
rem  VM_COUNT  Number of virtual machines
rem  Set the number of config.plist to be used
for /f "tokens=* delims=" %%a in (ip_list.txt) do (
	set /a plist_num+=1
	REM   ssh  -o StrictHostKeyChecking=no  cc@192.168.122.190  '/Users/wx/auto_install.sh'
	ssh  -o StrictHostKeyChecking=no  wx@%%a   '/Users/wx/mount_efi.sh'  >> run.log  2>&1
	scp %plist_path%\config_!plist_num!.plist  wx@%%a:/Volumes/EFI/CLOVER/config.plist  >> run.log  2>&1
	start cmd /k ssh  -o StrictHostKeyChecking=no  wx@%%a  '/Users/wx/auto_install.sh'
)
echo start revise kbjfrfpoJU ,Please wait  .................

pause
