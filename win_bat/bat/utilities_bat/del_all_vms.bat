@echo off
set BASE_DIR=%cd%
REM Set the template VM path
set TEMPLATE_PATH=%BASE_DIR%\..\..\TemplateVM\macos10.15
REM Set the storage path of the target VM
set VM_BASE_PATH=%BASE_DIR%\..\..\NewVM
REM Set the number of virtual machines that need to be created
set VMRUN_PATH="C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe" 
rem 遍历目录下所有的 .vmx 
for /r "%VM_BASE_PATH%" %%f in (*.vmx) do (
   rem    "%VMRUN_PATH%" start "%%f" nogui
   if /i "%%~xf"==".vmx"  (
        echo stopping  vm: %%f
        %VMRUN_PATH% stop "%%f" nogui 
		rem nogui
    ) else (
       rem   echo skip : %%f 
    )
)
echo  Start deleting virtual machine files!.............
if exist "%VM_BASE_PATH%" (
    echo Deleting all subfolders in "%VM_BASE_PATH%"...
    for /d %%D in ("%VM_BASE_PATH%\*") do (
        rmdir /s /q "%%D"
    )
    echo All virtual machine folders have been deleted!.............
) else (
    echo The target directory does not exist.
)

pause


