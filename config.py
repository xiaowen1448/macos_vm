# 全局配置文件
# Global Configuration File

# 项目根目录
project_root = r'D:\xiaowen_1448\macos_vm'


# 用户认证信息
USERNAME = 'admin'
PASSWORD = '123456'

# 模板虚拟机路径
template_dir = f'{project_root}\\TemplateVM'

# 虚拟机克隆目录
clone_dir = f'{project_root}\\NewVM\\10.12_clone'

# 临时虚拟机目录
vm_temp_dir = f'{project_root}\\NewVM\\10.12_clone'

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
    f'{project_root}\\macos_script\\macos_sh',
    f'{project_root}\\macos_script\\macos_scpt'
]

# 兼容性：保持原有的单一目录配置（已废弃，请使用script_upload_dirs）
script_upload_dir = f'{project_root}\\macos_script\\macos_sh'


# 虚拟机macos用户名
vm_username = 'wx'

# 虚拟机macos密码
vm_password = '123456'

# 脚本远端上传路径（根据用户名动态变化）
script_remote_path = f'/Users/{vm_username}/Documents/macos_sh/'

# 引导配置路径
boot_config_path = '/Volumes/EFI/CLOVER/config.plist'


# 日志目录
logs_dir = r'logs'

#ScptRunner客户端安装路径
ScptRunner_path=f'/Users/wx/Documents/ScptRunner/'

#ScptRunner客户日志路径
ScptRunner_path=f'/Users/wx/Documents/ScptRunner/logs/'


#appleid临时文本路径
appleidtxt_path=f'/Users/wx/Documents/'


# VNC端口起始值（用于端口递增分配）
vnc_start_port = 5918
# 当前分配的最大VNC端口（用于端口递增分配）

# VNC默认密码
vnc_default_password = '123456'