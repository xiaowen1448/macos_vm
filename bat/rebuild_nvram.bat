@setlocal enabledelayedexpansion
@echo off
set BASE_DIR=%cd%
set TEMPLATE_PATH=%BASE_DIR%\..\TemplateVM\macos10.15
REM Set the storage path of the target VM
set VM_BASE_PATH=%BASE_DIR%\..\NewVM
REM Set the number of virtual machines that need to be created
set VM_COUNT=4
set VMRUN_PATH="C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"
rem  stop  vms 
call stop_all_vms.bat
rem  copy  nvram  
for /r "%VM_BASE_PATH%" %%f in (*.*) do (
   rem    "%VMRUN_PATH%" start "%%f" nogui
   if /i "%%~xf"==".nvram"  (
    rem  echo %%f
	rem   %VMRUN_PATH%  stop  %%f nogui
	echo "%%f starting  rebuilding NVRM  ..............  "
	copy /y  "%TEMPLATE_PATH%\macos10.15.nvram"    %%f  >> log\run.log  2>&1
    echo "%%f  rebuilding  NVRM Complete  ..............  "
    )else (
   rem   echo Value is unknown
)
)
call start_all_vms.bat
echo  "All virtual machines NVRM have been rebuilt ..............""
echo "All virtual machines have been started .............."
pause
