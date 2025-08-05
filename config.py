# VirtualBox监控系统配置文件

# VirtualBox虚拟机目录路径
# 留空则使用默认路径
VBOX_DIR = r"D:\Users\wx\VirtualBox VMs"

# 虚拟机克隆目录
clone_dir = r'D:\macos_vm\NewVM\10.12_clone'

# 成品虚拟机目录
vm_chengpin_dir = r'D:\macos_vm\NewVM\chengpin_vm'

# 用户认证信息
USERNAME = 'admin'
PASSWORD = '123456'

# 模板虚拟机路径
template_dir = r'D:\macos_vm\TemplateVM'

# vmrun运行路径
vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'

# plist模板配置文件目录
plist_template_dir = r'web\config\plist'

# 五码配置文件目录
wuma_config_dir = r'web\config\config_unused'

# 配置已删除五码目录
wuma_config_delete_dir = r'web\config\config_delete'

# 配置已使用五码目录
wuma_config_install_dir = r'web\config\config_install'

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

# VirtualBox可执行文件路径
# 设置为"auto"表示自动检测，或留空使用默认检测
VBOXMANAGE_PATH = r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"

# 监控间隔（秒）
MONITOR_INTERVAL = 60

# Web服务端口
WEB_PORT = 5000

# Web服务主机
WEB_HOST = "0.0.0.0"

# 日志级别
LOG_LEVEL = "DEBUG"

# 自动启动已停止的虚拟机
AUTO_START_STOPPED_VMS = True

# 日志文件路径
import datetime
current_date = datetime.datetime.now().strftime('%Y-%m-%d')
LOG_FILE = f"{logs_dir}/vbox_monitor_{current_date}.log"

# Web日志文件路径
WEB_LOG_FILE = f"{logs_dir}/vbox_web_{current_date}.log"

# 日志格式
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

# 日志编码
LOG_ENCODING = "utf-8"

# 是否启用详细日志
VERBOSE_LOGGING = True

# 是否启用文件日志
ENABLE_FILE_LOGGING = True

# 是否启用控制台日志
ENABLE_CONSOLE_LOGGING = True

# 日志文件最大大小（MB）
LOG_FILE_MAX_SIZE = 100

# 日志文件保留天数
LOG_FILE_RETENTION_DAYS = 30

# 是否启用API调试日志
ENABLE_API_DEBUG = True

# 是否启用前端调试日志
ENABLE_FRONTEND_DEBUG = True

# 是否启用命令执行调试日志
ENABLE_COMMAND_DEBUG = True

# 是否启用状态检查调试日志
ENABLE_STATUS_DEBUG = True

# 虚拟机状态检查超时时间（秒）
VM_STATUS_TIMEOUT = 10

# 虚拟机启动超时时间（秒）
VM_START_TIMEOUT = 60

# 虚拟机停止超时时间（秒）
VM_STOP_TIMEOUT = 30

# 扫描虚拟机超时时间（秒）
SCAN_VMS_TIMEOUT = 10

# 获取虚拟机信息超时时间（秒）
VM_INFO_TIMEOUT = 10

# 是否启用详细日志
VERBOSE_LOGGING = True

# 是否在启动时自动扫描虚拟机
AUTO_SCAN_ON_START = True

# 是否在监控时显示详细状态
SHOW_DETAILED_STATUS = True

# Web界面自动刷新间隔（秒）
WEB_AUTO_REFRESH_INTERVAL = 30

# 监控线程是否为守护线程
MONITOR_THREAD_DAEMON = True

# 是否启用Web界面
ENABLE_WEB_INTERFACE = True

# 是否启用API接口
ENABLE_API_INTERFACE = True

# 是否启用自动监控功能
ENABLE_AUTO_MONITORING = True

# 是否启用自动启动功能
ENABLE_AUTO_START = True

# 是否启用详细错误信息
SHOW_DETAILED_ERRORS = True

# 虚拟机状态映射（中文显示）
VM_STATUS_MAPPING = {
    'running': '运行中',
    'poweroff': '已关闭',
    'paused': '已暂停',
    'saved': '已保存',
    'aborted': '异常终止',
    'unknown': '未知状态'
}

# 虚拟机状态颜色映射
VM_STATUS_COLORS = {
    'running': 'success',
    'poweroff': 'secondary',
    'paused': 'warning',
    'saved': 'info',
    'aborted': 'danger',
    'unknown': 'dark'
}

# 虚拟机状态图标映射
VM_STATUS_ICONS = {
    'running': 'fas fa-play',
    'poweroff': 'fas fa-stop',
    'paused': 'fas fa-pause',
    'saved': 'fas fa-save',
    'aborted': 'fas fa-exclamation-triangle',
    'unknown': 'fas fa-question'
}

# VirtualBox可执行文件常见路径
VBOXMANAGE_POSSIBLE_PATHS = [
    r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
    r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
    "/usr/bin/VBoxManage",
    "/usr/local/bin/VBoxManage",
    "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage"
]

# 是否启用自动检测VirtualBox路径
AUTO_DETECT_VBOXMANAGE = True

# VirtualBox启动类型
# 可选值: headless, gui, sdl
VBOX_START_TYPE = "headless"

# 监控虚拟机状态功能
# 是否启用监控虚拟机状态功能
ENABLE_VM_STATUS_MONITORING = True

# 监控虚拟机状态间隔（秒）
VM_STATUS_MONITOR_INTERVAL = 30

# 是否在Web界面显示监控虚拟机状态按钮
SHOW_VM_STATUS_MONITOR_BUTTON = True

# 母盘虚拟机配置
# 母盘虚拟机名称列表（这些虚拟机将被排除在自动启动之外）
MASTER_VM_EXCEPTIONS = [
    "TemplateVM",
    "BaseVM", 
    "MasterVM",
    "Template",
    "Base"
]

# 是否启用母盘虚拟机例外功能
ENABLE_MASTER_VM_EXCEPTIONS = True

# 选中的虚拟机目录配置
# 用户选择的虚拟机目录路径
SELECTED_VM_DIRECTORIES = [
    r"D:\Users\wx\VirtualBox VMs"
]

# 是否启用多目录监控
ENABLE_MULTI_DIRECTORY_MONITORING = True

# 是否在Web界面显示目录选择功能
SHOW_DIRECTORY_SELECTION = True

# 监控配置
# 是否启用实时状态监控
ENABLE_REALTIME_STATUS_MONITORING = True

# 状态监控更新间隔（秒）
STATUS_UPDATE_INTERVAL = 15

# 是否在状态变化时发送通知
ENABLE_STATUS_CHANGE_NOTIFICATIONS = True

# 监控按钮配置
# 监控按钮显示文本
MONITOR_BUTTON_TEXT = "监控虚拟机状态"

# 监控按钮图标
MONITOR_BUTTON_ICON = "fas fa-eye"

# 监控按钮颜色类
MONITOR_BUTTON_COLOR = "btn-primary"

# 是否显示监控状态指示器
SHOW_MONITOR_STATUS_INDICATOR = True

# 监控状态指示器颜色
MONITOR_STATUS_INDICATOR_COLORS = {
    'active': 'success',
    'inactive': 'secondary',
    'error': 'danger'
}

# 自动监控配置
# 是否启用自动监控
ENABLE_AUTO_MONITORING = True

# 默认自动监控间隔（秒）
DEFAULT_AUTO_MONITOR_INTERVAL = 30

# 是否默认启用自动启动未运行的虚拟机
DEFAULT_AUTO_START_ENABLED = False

# 自动监控配置保存
AUTO_MONITOR_CONFIG = {
    'enabled': True,
    'interval': 30,
    'auto_start_enabled': False
}
