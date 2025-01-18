@setlocal enabledelayedexpansion
@echo off
REM 设置模板虚拟机路径
set TEMPLATE_PATH=D:\macos_vm\TemplateVM\macos10.15

REM 设置目标虚拟机存放路径
set VM_BASE_PATH=D:\macos_vm\NewVM


rem 禁用appleid 提醒
REM 执行批量创建
for /f "tokens=* delims=" %%a in (ip_list.txt) do (
	REM   ssh  -o StrictHostKeyChecking=no  cc@192.168.122.190  '/Users/wx/auto_install.sh'
	  start cmd /k ssh  -o StrictHostKeyChecking=no  wx@%%a  '/Users/wx/disable_appleAlert.sh'  > run_ssh_output%%a.txt
)

echo "All virtual machines have been copy   done  ."
pause
