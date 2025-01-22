1.克隆虚拟机脚本运行run_vm_clone.bat  ，这一步实现，vmdk等文件夹的复制，和虚拟机文件夹你的创建，每个为单独独立

![image](https://github.com/user-attachments/assets/7113ac86-9e0b-494d-9dce-e7ec078724c4)

克隆完毕后回获取每个虚拟机的IP地址，执行ssh 命令脚本和scp命令脚本，此步骤实现，挂在efi分区，和拷贝成品的config.plist ,之后执行批量重启安装macos的步骤
![image](https://github.com/user-attachments/assets/e71949bc-3e44-4b07-a0b1-9ee8cbe82675)


等待macos安装完毕，会成功更改kbjfrfpoJU值，执行disable_appleAlert.bat ,禁用appleid登录提示。

执行rebuild_nvram.bat，重装后，macosx引导会覆盖原有的clover引导，执行此脚本更改bios引导顺序，使用默认的nvram则使用clover引导，五码可正常识别

最后需要执行auto_Send_vmkey.bat  ，输入系统密码，已实现重装后的macos用户自动登录步骤

最后重启后，会生成最终的唯一的macos虚拟机
