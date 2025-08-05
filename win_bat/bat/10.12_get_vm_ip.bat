@setlocal enabledelayedexpansion
@echo off
set  BASE_DIR=%cd%
REM Set the storage path of the target VM
set VM_BASE_PATH=%BASE_DIR%\..\NewVM
set IP_PATH=%BASE_DIR%\var_files
set ISO_BASE_HOME=%BASE_DIR%\..\iso
set LOG_PATH=%BASE_DIR%\var_files
set plist_num=0
copy /y nul %IP_PATH%\10.12_ip_list.txt  >> %LOG_PATH%\run.log   2>&1
set VMRUN_PATH=vmrun
REM vmx files path 10.12_vmx_list.txt
set var_time=%1
REM  echo %var_time%
:check
copy /y nul %IP_PATH%\10.12_ip_list.txt  >> %LOG_PATH%\run.log   2>&1
for /f "delims=" %%a in (%IP_PATH%\10.12_vmx_list.txt) do (
	set /a plist_num+=1
	rem  echo plist_num:!plist_num!
	set VM_EXE=%VMRUN_PATH% getGuestIPAddress %%a
	for /f %%i in ('!VM_EXE!') do set VAR_IP=%%i
	echo !VAR_IP! | findstr /r "^[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*"  >> %LOG_PATH%\run.log  2>&1  
	if !errorlevel! equ 0 (
	echo vmx is :%%a
	echo ipaddress is :!VAR_IP!
	echo !VAR_IP! >>  %IP_PATH%\ip_list.txt 
	) else (
	echo  Please wait the VM %%a to Restarting ! .............
	timeout /t %var_time% >> %LOG_PATH%\run.log  2>&1  
	goto check
	)
)





