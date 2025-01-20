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
set VM_COUNT=4
set VMRUN_PATH="C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"
rem  Random numbers start
set sum=15
set num=1
rem set vmnet_ip=192.168.119.1
set nmap_count=253
rem  memory size 
set memsize="2048"
set plist_path=%BASE_DIR%\..\plist\chengpin
set plist_num=0
echo  "" > log\run.log
REM Perform batch creation
for /L %%i in (1,1,%VM_COUNT%) do (
    REM Create a new virtual machine directory
    set VM_DIR=%VM_BASE_PATH%\VM_%%i
	set /a sum=!sum!+%%i
    mkdir !VM_DIR!
    REM Copy the template VM file
    xcopy /E /I %TEMPLATE_PATH% !VM_DIR!  >> log\run.log  2>&1
    echo  displayName = "macos10.15_%%i" >>  "!VM_DIR!\macos10.15.vmx"
	echo  sata0:0.fileName = "macos10.15_%%i.vmdk"  >>  "!VM_DIR!\macos10.15.vmx"
	echo  nvram = "macos10.15_%%i.nvram"  >>  "!VM_DIR!\macos10.15.vmx" 
	echo  extendedConfigFile = "macos10.15_%%i.vmxf" >> "!VM_DIR!\macos10.15.vmx" 
	rem  iso\Installer_macOS_Catalina_10.15.7.iso
	echo sata0:1.fileName = "%ISO_BASE_HOME%\Installer_macOS_Catalina_10.15.7.iso"  >>  "!VM_DIR!\macos10.15.vmx" 
	echo  memsize="2048" >> "!VM_DIR!\macos10.15.vmx"
	REM nvram = "macOS 10.15.nvram"  bios  
	REM displayName = "macOS 10.15"
	REM sata0:0.fileName = "macOS 10.15.vmdk"
	REM extendedConfigFile = "macOS 10.15.vmxf"
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
rem   the virtual machine to starting   please wait    .................... 
rem   Wait for the VM to start up and obtain the IP address of the VM
rem  timeout /t 240 
echo The IP address is being scanned, please wait .................... 
REM  Define the range of nmap scan addresses  for Example   192.168.119.2-10
rem for /f "tokens=1,2,3,4 delims=." %%a in ("%vmnet_ip%") do (
rem 	set /a result_d=%%d + %num%
rem 	set new_vmnet_ip=%%a.%%b.%%c.!result_d!
rem )
rem  echo !new_vmnet_ip!-%nmap_count%
rem  nmap !new_vmnet_ip!-%nmap_count%  > %IP_PATH%\example.txt 
rem awk -F: "/report/{ print $0 }" %IP_PATH%\example.txt | awk -F" " "{ print $NF }"  > %IP_PATH%\ip_list.txt  
rem sed -i  "s/(//g"  %IP_PATH%\ip_list.txt 
rem sed -i  "s/)//g"  %IP_PATH%\ip_list.txt
rem  del sed*
rem  echo  "IP address information is saved in this text  ip_list.txt"
rem echo nmap ip address  is done   ....................
echo  Obtaining the IP address of the VM is in progress!......................
:check
call ip_find.bat
rem  echo %errorlevel%
if %errorlevel% neq 0 (
echo  The VM IP was not found  Waiting for 10 seconds, press a key to continue... ......................
timeout /t 10
call get_VM_IPAddress.bat
goto check     
) else (
echo echo  IP address information is saved in %IP_PATH%\ip_list.txt!......................
)
echo Start executing scripts in batches  ............................
rem  VM_COUNT  Number of virtual machines
rem  Set the number of config.plist to be used
for /f "tokens=* delims=" %%a in (%IP_PATH%\ip_list.txt) do (
	set /a plist_num+=1
	REM   ssh  -o StrictHostKeyChecking=no  cc@192.168.122.190  '/Users/wx/auto_install.sh'
	ssh  -o StrictHostKeyChecking=no  wx@%%a   '/Users/wx/mount_efi.sh'  >> log\run.log  2>&1
	scp %plist_path%\config_!plist_num!.plist  wx@%%a:/Volumes/EFI/CLOVER/config.plist  >> log\run.log  2>&1
	start cmd /k ssh  -o StrictHostKeyChecking=no  wx@%%a  '/Users/wx/auto_install.sh'
)
echo start revise kbjfrfpoJU ,Please wait  .................

pause
