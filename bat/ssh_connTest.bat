@setlocal enabledelayedexpansion
@echo off
set BASE_DIR=%cd%
set TEMPLATE_PATH=%BASE_DIR%\..\TemplateVM\macos10.15
REM Set the storage path of the target VM
set VM_BASE_PATH=%BASE_DIR%\..\NewVM
set IP_PATH=%BASE_DIR%\var_files
set VMRUN_PATH="C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe" 
rem  Obtain the IP address of the VM
get_vm_ip.bat

rem  check  file  ip_list.txt
type  %IP_PATH%\ip_list.txt

