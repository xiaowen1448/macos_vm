@setlocal enabledelayedexpansion
@echo off

set num=1
set vmnet_ip=192.168.119.1
for /f "tokens=1,2,3,4 delims=." %%a in ("%vmnet_ip%") do (
	set /a result_d=%%d + %num%
	set new_vmnet_ip=%%a.%%b.%%c.!result_d!
	
)
echo !new_vmnet_ip!
pause
