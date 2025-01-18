@setlocal enabledelayedexpansion
@echo off


echo " vm  starting   ...................."


echo  "The IP address is being scanned, please wait    ...................."

nmap 192.168.119.2-200  > example.txt

awk -F: "/report/{ print $0 }" example.txt  | awk -F" " "{ print $5 }" > ip_list.txt

echo  "ip  list  output  ip_list.txt"


echo  "ip address  is done   ...................."




echo  " run  ssh  going  ............................"


for /f "tokens=* delims=" %%a in (ip_list.txt) do (
	
	REM   ssh  -o StrictHostKeyChecking=no  cc@192.168.122.190  '/Users/cc/auto_install.sh'
	
	  start cmd /k ssh  -o StrictHostKeyChecking=no  wx@%%a  '/Users/wx/Desktop/auto_install.sh'  > run_ssh_output%%a.txt
)

echo   "start revise   JU  ，Please wait  ................."

