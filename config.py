# 全局配置文件
# Global Configuration File

# 用户认证信息
USERNAME = 'admin'
PASSWORD = '123456'

# 模板虚拟机路径
template_dir = r'D:\macos_vm\TemplateVM'

# 虚拟机克隆目录
clone_dir = r'D:\macos_vm\NewVM\10.12_clone'

# 克隆后成品虚拟机路径
vm_chengpin_dir = r'D:\macos_vm\NewVM\chengpin_vm'

# vmrun运行路径
vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'

# plist模板配置文件目录
plist_template_dir = r'config\plist'

# 五码配置文件目录
wuma_config_dir = r'config\config_unused'

# 配置已删除五码目录
wuma_config_delete_dir = r'config\config_delete'

# 配置已使用五码目录
wuma_config_install_dir = r'config\config_install'

# 脚本本地上传路径
script_upload_dir = r'D:\macos_vm\macos_sh'


# 虚拟机macos用户名
vm_username = 'wx'

# 虚拟机macos密码
vm_password = '123456'

# 脚本远端上传路径（根据用户名动态变化）
script_remote_path = f'/Users/{vm_username}/'

# 引导配置路径
boot_config_path = '/Volumes/EFI/CLOVER/config.plist'

# 项目根目录
project_root = r'D:\macos_vm'

# 日志目录
logs_dir = r'logs'

# 工具目录
tools_dir = r'tools'

# EFI目录
efi_dir = r'EFI'

# ISO目录
iso_dir = r'iso'

# 批处理脚本目录
bat_dir = r'bat'

# Python工具目录
py_util_dir = r'py_util'

# Web应用目录
web_dir = r'web'

# NVRAM目录
nvram_dir = r'nvrm' 