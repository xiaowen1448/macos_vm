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
rem  call get_vm_ip.bat 30
type %IP_PATH%\ip_list.txt
echo Start executing scripts in batches  ............................
rem  VM_COUNT  Number of virtual machines
rem  Set the number of config.plist to be used
for /f "tokens=* delims=" %%a in (%IP_PATH%\ip_list.txt) do (	
	set /a plist_num+=1
	rem 尝试 SSH 登录
	echo %ssh_uname%@%%a
	ssh  -o StrictHostKeyChecking=no  %ssh_uname%@%%a  exit   >> %LOG_PATH%\run.log  2>&1
	rem 检查 SSH 登录的返回码
	echo %ERRORLEVEL%===============
if %ERRORLEVEL% equ 0 (
    echo SSH login successful.
) else (
    echo SSH login failed.
)
)

pause