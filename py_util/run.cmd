rem  调用五码生成配置文件
rem  虚拟机克隆的数量要和五码数量一致,确保五码充足可用
cd  /d ..\plist\
rem  开始读取五码配置文件，开始批量生成成品plist
call   ..\plist\run_plist.bat
rem  开始执行自动克隆，更改ju值，分配五码
python  test.py