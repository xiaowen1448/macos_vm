@setlocal enabledelayedexpansion
@echo off
set BASE_DIR=%cd%
set TEMPLATE_PATH=%BASE_DIR%\..\TemplateVM\macos10.15
REM Set the storage path of the target VM
set VM_BASE_PATH=%BASE_DIR%\..\NewVM
set IP_PATH=%BASE_DIR%\ip
REM Set the number of virtual machines that need to be created
set VM_COUNT=4
set VMRUN_PATH="C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe" 
del  %IP_PATH%\ip_list.txt
for /r "%VM_BASE_PATH%" %%f in (*.vmx) do (
   rem    "%VMRUN_PATH%" start "%%f" nogui
   if /i "%%~xf"==".vmx"  (
    %VMRUN_PATH% getGuestIPAddress  %%f  >>  %IP_PATH%\ip_list.txt
    )else (
   rem   echo Value is unknown
)
)
echo  vms ipaddress is done  ! ...............
rem  type %IP_PATH%\ip_list.txt



