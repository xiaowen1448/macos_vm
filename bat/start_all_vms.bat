@echo off
set BASE_DIR=%cd%
REM Set the template VM path
set TEMPLATE_PATH=%BASE_DIR%\..\TemplateVM\macos10.15
REM Set the storage path of the target VM
set VM_BASE_PATH=%BASE_DIR%\..\NewVM
REM Set the number of virtual machines that need to be created
set VMRUN_PATH=vmrun
rem 遍历目录下所有的 .vmx 文件并启动
for /r "%VM_BASE_PATH%" %%f in (*.vmx) do (
   rem    "%VMRUN_PATH%" start "%%f" nogui
   if /i "%%~xf"==".vmx"  (
        echo starting  vm: %%f
        %VMRUN_PATH% start "%%f" nogui 
		rem nogui
    ) else (
       rem   echo skip : %%f 
    )
)
echo "All virtual machines have been started .............."

pause