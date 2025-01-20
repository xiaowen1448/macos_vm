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
copy /y nul %IP_PATH%\ip_list.txt  >> log\run.log  2>&1
for /r "%VM_BASE_PATH%" %%f in (*.vmx) do (
   rem    "%VMRUN_PATH%" start "%%f" nogui
   if /i "%%~xf"==".vmx"  (
    REM  %VMRUN_PATH% getGuestIPAddress  %%f  >>  %IP_PATH%\ip_list.txt
	set VM_EXE=%VMRUN_PATH% getGuestIPAddress  %%f 
	for /f %%i in ('!VM_EXE!') do set VAR_IP=%%i
	echo !VAR_IP! | findstr /r "^[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*"  >> log\run.log  2>&1
	if !errorlevel! equ 0 (
	%VMRUN_PATH% getGuestIPAddress  %%f  >>  %IP_PATH%\ip_list.txt
	) else (
	copy /y nul %IP_PATH%\ip_list.txt  >> log\run.log  2>&1
	echo  Please wait for the virtual machine %%f to restart ! .............
	timeout /t 10 >> log\run.log  2>&1
	call get_vm_ip.bat 
)
    )else (
   rem   echo Value is unknown
)
)
rem  type %IP_PATH%\ip_list.txt



