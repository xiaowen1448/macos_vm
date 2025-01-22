脚本解释

macos_sh 脚本均需要远端使用ssh命令调用

auto_install.sh 负责执行无人值守安装。

auto_send_key.sh 使用osascript实现自动输入密码登录

disable_appleAlert.sh 禁用appleid提示，

iMessageDebug 获取macos五码及uuid等值

mount_efi.sh 挂载clover EFIF分区用于修改五码

random_hostname.sh 开机自启的uuid主机名，避免主机名冲突

reboot.sh 重启脚本，也可使用reboot命令，实现重启即可
