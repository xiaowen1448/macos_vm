批量实现克隆虚拟机需求，要求实现每台虚拟机ju值为唯一，五码后续更改有批量生成的confi.plist文件实现替换，实现uuid，五码每台为唯一
imessagedebug输出如下
wx@bogon ~ % /Users/wx/Desktop/iMessageDebug ; exit;
SmUUID: failed
**********************iMessage Debug**********************
Credits: ElNono, mdmwii,flux84, sugarface, pokenguyen


              Model: VMware20,1
           Board-id: Mac-AA95B1DDAB278B95
       SerialNumber: VMLbH9Kbb8Q4
      Hardware UUID: 564D9976-62CB-847F-619E-157CB36A4660

          System-ID: failed
                ROM: 564d997662cb
  BoardSerialNumber: hH9hnhV8s2pGYA...

         Gq3489ugfi: 3719cd7c333ab35387fcb32d088d7087fc
          Fyp98tpgj: ba5969a6b702e9d3f7bcc2b7f0d2307a0a
         kbjfrfpoJU: 39feee3569700187b9e15f700427984e20
       oycqAZloTNDm: c3c5004bcba694b857bc5fc61b82ff6915
       abKPld1EcMni: e4eead6a92076fd3104f3e6eede0d51da3

Do you want to save to iMessageDebug.txt? (y/n) 


windows 环境配置
======================================================
需要支持
ssh scp 用于远程登录macos虚拟机免密执行某个脚本,scp用于远程拷贝文件到虚拟机，无此命令，参考百度下载OpenSSH或者某些工具，添加进入系统环境变量即可

ssh-keygen  添加本机密钥，拷贝到虚拟机，实现免密登录 ，默认生成文件夹路径为 参考：为我的用户为wx，目录为C:\Users\wx\.ssh\id_ed25519.pub

awk  安装awk百度参考下载链接，添加进入系统环境变量的即可

sed  安装sed 百度参考下载链接，添加进入系统环境变量的即可

uuidgen  需要安装windows VisualStudio，安装选择c++桌面开发，或者使用powershell,用于clover中SMUUID和CustomUUID确保唯一性如下：
---------------------------------------------------------
C:\Users\wx>powershell -Command  [guid]::NewGuid()

Guid
----
fc2fdd4a-2d58-40a1-8dee-c996410daa18

C:\Users\wx>


C:\Users\wx>uuidgen
48835612-b80d-4fc0-b02d-a74d55e14115

C:\Users\wx>where uuidgen
C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\uuidgen.exe

C:\Users\wx>

--------------------------------------------------
==========================================================

模板虚拟机实现：

纯净版本的iso安装文件获取，搜索各大网站获取。或者利用macos操作系统制作可引导的安装iso文件

制作macos  iso 文件参见文档，来源于chatgpt macos制作可以启动的iso引导文件.docx

安装全新的macos虚拟机，并注入，clover或者Oencore引导，bios设置clover或者opencore引导为第一位，
控制台端电脑需和macos模板虚拟机添加互信实现免密登录，远程免密拷贝文件，这样克隆出的虚拟机没太都是互信。可实现批量免密控制
添加自动执行脚本保存为sh，添加执行权限，例如
auto_install.sh  脚本功能实现命令行超级权限执行重装macos ,重启后生效，已实现更改ju值
disable_appleAlert.sh    脚本实现重装后禁用appleid提示，重启后生效
mount_efi.sh  	脚本功能为实现挂载磁盘efi分区,更改config.plist 由scp远程实现
reboot.sh  		脚本实现重启操作系统
重建nvrm.bat  重装macos后会改变clover和macosx的引导顺序，将原有定义好的bios信息也就是nvrm文件替换。
单独保存vmdk，nvrm文件其余不要，保存文件夹为macos10.15，

新建测试虚拟机，编辑磁盘为80G ，网卡接入为nat，镜像文件为iso，新建后将vmx文件拷贝出来

编辑vmx文件添加bios.bootDelay = "1000"，方便后期按F2进行调试

删除以下参数
displayName = "macos10.15_1"   #为macos虚拟机的名称
sata0:0.fileName = "macos10.15_1.vmdk"   #macos 虚拟机磁盘
nvram = "macos10.15_1.nvram"       #macos虚拟机的bios信息
extendedConfigFile = "macos10.15_1.vmxf"     

以上参数脚本会自动更改，实现每台虚拟机都是唯一的名字，避免虚拟机开机后会提示冲突

批量复制完成会自动启动虚拟机，

使用使用namp扫描同网段获取maco的ip地址，

免密登录，执行重启安装脚本

安装成功，继续执行disable_appleAlert.sh 禁用提示appleid  

批量克隆步骤实现批量复制虚拟机目录，脚本修改vmc配置文件，实现每台虚拟机名称对应的配置文件是唯一的，开机后不会提示已复制和已移动，每台为唯一

ju值更改之后，需要实现批量更改五码，重启后生效

更改五码，五码文本来源于，使用脚本批量分割后，批量生成成品的唯一的config.plist 分发给虚拟机，执行远程复制，远程重启，更改五码成功



至此，批量克隆虚拟机，更改ju，更改五码实现。



