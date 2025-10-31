# 全局配置文件
# Global Configuration File
# 导入日志模块
import os
import logging
# 配置日志级别（供其他模块使用）
LOG_LEVEL = logging.INFO
# 项目根目录
project_root = r'D:\xiaowen_1448\macos_vm'
# 应用根目录（为了兼容性）
app_root = project_root
#脚本项目根目录
macos_script_project_root = r'D:\xiaowen_1448\macos_script'
# 用户认证信息
USERNAME = 'admin'
PASSWORD = '123456'
# 虚拟机macos用户名
vm_username = 'wx'
# 虚拟机macos密码
vm_password = '123456'
# VNC端口起始值（用于端口递增分配）
vnc_start_port = 5918
# 当前分配的最大VNC端口（用于端口递增分配）
# VNC默认密码
vnc_default_password = '123456'
#虚拟机macos远端家目录
vm_macos_home_dir = f'/Users/{vm_username}'
# 模板虚拟机路径
template_dir = f'{project_root}\\TemplateVM'
# 虚拟机克隆目录
clone_dir = f'{project_root}\\NewVM\\10.12_clone'
# 临时虚拟机目录
vm_temp_dir = clone_dir
# 临时文件目录
temp_dir = f'{project_root}\\temp'
vm_base_dir= f'{project_root}\\NewVM'
# 克隆后成品虚拟机路径
vm_chengpin_dir = f'{project_root}\\NewVM\chengpin_vm'
# vmrun运行路径
vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
web_base_dir=r'web\\config'
# plist模板配置文件目录
plist_template_dir = f'{web_base_dir}\\plist'
# plist成品模板配置文件目录
plist_chengpin_template_dir = f'{web_base_dir}\\chengpin_plist'
# 五码配置文件目录
wuma_config_dir = f'{web_base_dir}\\config_unused'
# 配置已删除五码目录
wuma_config_delete_dir = f'{web_base_dir}\\config_delete'
# 配置已使用五码目录
wuma_config_install_dir = f'{web_base_dir}\\config_install'

# icloud管理中需要默认五码配置文件
default_wuma_config = '14.1五码.txt'
# Apple ID未使用目录
appleid_unused_dir = f'{web_base_dir}\\ID_unused'
# Apple ID已删除目录
appleid_delete_dir = f'{web_base_dir}\\ID_delete'
# Apple ID已使用目录
appleid_install_dir = f'{web_base_dir}\\ID_install'
# 发信手机号未使用目录
phone_unused_dir = f'{web_base_dir}\\phone_unused'
# 发信手机号已删除目录
phone_delete_dir = f'{web_base_dir}\\phone_delete'
# 脚本本地上传路径（支持多个目录）
script_upload_dirs = [
    f'{macos_script_project_root}\\macos_sh',
    f'{macos_script_project_root}\\macos_scpt'
]
# 兼容性：保持原有的单一目录配置（已废弃，请使用script_upload_dirs）
script_upload_dir = f'{macos_script_project_root}\\macos_script\\macos_sh'

# 脚本sh远端上传路径（根据用户名动态变化）
sh_script_remote_path = f'{vm_macos_home_dir}/Documents/macos_script/macos_sh/'
# 脚本scpt远端上传路径（根据用户名动态变化）
scpt_script_remote_path = f'{vm_macos_home_dir}/Documents/macos_script/macos_scpt/'
# 引导配置路径
boot_config_path = '/Volumes/EFI/CLOVER/config.plist'

oc_config_path='/Volumes/EFI/OC/config.plist'
# 日志目录
logs_dir = r'logs'
#ScptRunner客户端安装路径
ScptRunner_path=f'{vm_macos_home_dir}/Documents/ScptRunner/'
#ScptRunner客户日志路径
ScptRunner_logs_path=f'{vm_macos_home_dir}/Documents/ScptRunner/logs/'
#imessage脚本配置
#im登录脚本
login_imessage='login_imessage.scpt'
#imessage发送脚本
send_imessage='send_imessage.scpt'
#appleid临时文本路径
appleidtxt_path=f'{vm_macos_home_dir}/Documents/'
#lcoud处理脚本目录
macos_script_dir=f'{macos_script_project_root}\\macos_scpt\\macos11'
#重启ScptRunner脚本目录
restart_scptRunner=f'{scpt_script_remote_path}macos11/'
#待处理原文本
icloud_txt_path=f'{vm_macos_home_dir}/Desktop/icloud.txt'
#已处理的文本
icloud2_txt_path=f'{vm_macos_home_dir}/Desktop/icloud2.txt'
#错误id文本
error_txt_path=f'{vm_macos_home_dir}/Desktop/error.txt'

clash_config=f'{vm_macos_home_dir}/.config/clash/config.yaml'

# iCloud处理时间配置
# 查询成功后等待执行注销的时间（秒）
icloud_wait_after_query = 5
# AppleID登录脚本超时设置（秒）
appleid_login_timeout = 90
# 登录成功后等待执行查询的时间（秒）
icloud_wait_after_login = 10
