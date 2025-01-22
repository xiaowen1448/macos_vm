模板虚拟机配置修改如下

1.用户自动登录配置：用户和群组，下拉自动登录勾选当前用户。

![1737538923281](https://github.com/user-attachments/assets/bad1f3bc-04c8-4a0e-9482-8f8a7d5ed851)

2.和安全性与隐私：
auto_send_key.sh 脚本需要安全隐私里面开启终端访问权限，远程ssh调用执行则需要sshd-keygen-wrapper,铺助功能勾选，vmware-tools-daemon ，允许终端访问此电脑

 ![image](https://github.com/user-attachments/assets/7c4928c8-e7b9-4f09-9896-f99d4b4ca1fe)

按需配置: 关闭屏幕休眠

 ![image](https://github.com/user-attachments/assets/520bded3-864a-44eb-b311-46c45011d4bb)

完全磁盘访问权限:为sshd
  ![image](https://github.com/user-attachments/assets/bb9885b2-1b0d-45da-9f3a-dc6467cf5136)
  
文件和文件夹修改为:勾选sshd,终端勾选可移除卷宗，桌面文件夹，
 ![image](https://github.com/user-attachments/assets/3b21822f-42ae-405a-b954-c7eecfb34e9b)

3.配置用户级别的开机自启动脚本，实现开机后随机主机名，比秒克隆大批量出现冲突，自启动脚本配置如下

![image](https://github.com/user-attachments/assets/64c2ff66-708e-421b-83dd-151bf642f92d)

更改脚本文件默认打开方式为终端

![image](https://github.com/user-attachments/assets/21f13b9b-1a9a-4ef0-852d-98f5dfd11be5)


终端设置：选择 shell 退出后关闭窗口：终端-偏好设置-描述文件-shell-当 shell 退出时。改下面为关闭窗口

![image](https://github.com/user-attachments/assets/e1ec6ae3-d923-4aca-8d7e-4864f7f895d0)


4.需要开启远程登录ssh，并加入客户密钥，登录互信配置
![image](https://github.com/user-attachments/assets/c2d17fa8-4fb5-48b5-8566-5e2496bff80c)

互信配置文件

![image](https://github.com/user-attachments/assets/bff45a27-8bd9-454e-9a84-545220b6465b)



