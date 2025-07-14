@setlocal enabledelayedexpansion
@echo off
REM Set the template VM path
set BASE_DIR=%cd%
set TEMPLATE_PATH=%BASE_DIR%\..\TemplateVM\macos10.15
REM Set the storage path of the target VM
set VM_BASE_PATH=%BASE_DIR%\..\NewVM
set ISO_BASE_HOME=%BASE_DIR%\..\iso
set IP_PATH=%BASE_DIR%\var_files
set LOG_PATH=%BASE_DIR%\var_files
REM Set the number of virtual machines that need to be created
set VM_COUNT=4
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
echo  Obtaining the IP address of the VM is in progress!......................
rem :check
rem  goto check 
copy /y nul %IP_PATH%\ip_list.txt  >> %LOG_PATH%\run.log  2>&1
call get_vm_ip.bat
type %IP_PATH%\ip_list.txt
echo Start executing scripts in batches  ............................
rem  VM_COUNT  Number of virtual machines
rem  Set the number of config.plist to be used
for /f "tokens=* delims=" %%a in (%IP_PATH%\ip_list.txt) do (
	set /a plist_num+=1
	ssh  -o StrictHostKeyChecking=no  %ssh_uname%@%%a   '/Users/%ssh_uname%/disable_appleAlert.sh'
	
)
echo disable_appleAlert is   done  !...............

