@setlocal enabledelayedexpansion
@echo off
REM 设置模板虚拟机路径
set TEMPLATE_PATH=D:\macos_vm\TemplateVM\macos10.15
REM 设置目标虚拟机存放路径
set VM_BASE_PATH=D:\macos_vm\NewVM
REM 设置需要创建的虚拟机数量
set VM_COUNT=4
rem  随机数起步
set sum=20
set plist_path=D:\macos_vm\plist\chengpin

for /f "tokens=* delims=" %%a in (ip_list.txt) do (
	set /a plist_num+=1
	ssh  -o StrictHostKeyChecking=no  wx@%%a  '/Users/wx/disable_appleAlert.sh'  >> run.log  2>&1
) 
for /L %%i in (1,1,%VM_COUNT%) do (
	set VM_DIR=%VM_BASE_PATH%\VM_%%i
	set /a sum=!sum!+%%i
	echo  "Virtual Machine %%i starts to stop ..............  "
	"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"    stop   !VM_DIR!\macos10.15_%%i.vmx nogui
	echo  "VM macos10.15_%%i  has stopped    ...............  "
	rem  move  "%TEMPLATE_PATH%\macos10.15.nvram"    "!VM_DIR!\macos10.15_%%i.nvram"
    echo "VM macos10.15_%%i starts rebuilding NVRM  ..............  "
	copy /y  "%TEMPLATE_PATH%\macos10.15.nvram"    "!VM_DIR!\macos10.15_%%i.nvram" >> run.log  2>&1
    echo "VM macos10.15_%%i rebuilds NVRM Complete  ..............  "
	echo "Start starting Virtual Machine macos10.15_%%i ..............   "
	"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"    start    !VM_DIR!\macos10.15_%%i.vmx nogui
	echo "VM macos10.15_%%i  has started ..............  "
)
echo  "All virtual machines NVRM have been rebuilt ..............""
echo "All virtual machines have been started .............."
pause