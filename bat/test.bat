@setlocal enabledelayedexpansion
@echo off
REM Set the template VM path
set BASE_DIR=%cd%
set TEMPLATE_PATH=%BASE_DIR%\..\TemplateVM\macos10.15
REM Set the storage path of the target VM
set VM_BASE_PATH=%BASE_DIR%\..\NewVM
set ISO_BASE_HOME=%BASE_DIR%\..\iso
set IP_PATH=%BASE_DIR%\ip
:check
call ip_find.bat
echo %errorlevel%
if %errorlevel% neq 0 (
echo  The VM IP was not found  Waiting for 10 seconds, press a key to continue... ......................
timeout /t 10
call get_VM_IPAddress.bat
goto check     
) else (
echo echo  IP address information is saved in %IP_PATH%\ip_list.txt!......................
)

