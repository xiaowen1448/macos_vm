# 全局配置文件说明

## 概述

本项目已实现全局配置系统，所有配置参数集中在 `config.py` 文件中管理。

## 配置文件位置

- 主配置文件: `config.py` (项目根目录)
- 测试文件: `test_config.py` (项目根目录)

## 配置参数说明

### 用户认证
```python
USERNAME = 'admin'          # Web应用登录用户名
PASSWORD = '123456'         # Web应用登录密码
```

### 虚拟机路径配置
```python
template_dir = r'D:\macos_vm\TemplateVM\macos10.12'           # 模板虚拟机路径
clone_dir = r'D:\macos_vm\NewVM\10.12'                        # 虚拟机克隆目录
vm_chengpin_dir = r'D:\macos_vm\NewVM\chengpin_vm'           # 克隆后成品虚拟机路径
```

### VMware工具配置
```python
vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'  # vmrun运行路径
```

### 虚拟机SSH配置
```python
vm_username = 'wx'          # 虚拟机macos用户名
vm_password = '123456'      # 虚拟机macos密码
```

### 脚本和配置路径
```python
web_config_dir = r'web\config'                                # 五码配置文件目录
script_upload_dir = r'D:\macos_vm\macos_sh'                  # 脚本上传路径
boot_config_path = '/Volumes/EFI/CLOVER/config.plist'        # 引导配置路径
```

### 项目目录结构
```python
project_root = r'D:\macos_vm'     # 项目根目录
logs_dir = r'logs'                # 日志目录
tools_dir = r'tools'              # 工具目录
efi_dir = r'EFI'                 # EFI目录
iso_dir = r'iso'                 # ISO目录
bat_dir = r'bat'                 # 批处理脚本目录
py_util_dir = r'py_util'         # Python工具目录
web_dir = r'web'                 # Web应用目录
nvram_dir = r'nvrm'              # NVRAM目录
```

## 使用方法

### 1. 在Python文件中导入配置

```python
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *

# 使用配置参数
print(f"模板路径: {template_dir}")
print(f"vmrun路径: {vmrun_path}")
```

### 2. 在Web应用中导入配置

```python
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *

# 使用配置参数
VM_DIRS = {
    '10_12': clone_dir,
    'chengpin': vm_chengpin_dir
}
```

### 3. 使用辅助函数

```python
# 获取vmrun路径（带备用路径检查）
vmrun_path = get_vmrun_path()

# 获取默认虚拟机目录
from py_util.util_vmx import get_default_vm_directories
vm_dirs = get_default_vm_directories()

# 获取默认SSH凭据
from py_util.util_ssh import get_default_ssh_credentials
ssh_creds = get_default_ssh_credentials()
```

## 已更新的文件

### Web应用
- `web/app.py` - 主要Web应用，已更新使用全局配置

### Python工具模块
- `py_util/main.py` - 主模块，已更新使用全局配置
- `py_util/run_vm_clone_10.12.py` - 虚拟机克隆模块
- `py_util/util_vmx.py` - VMX文件工具模块
- `py_util/util_ssh.py` - SSH连接工具模块
- `py_util/util_cmd.py` - 命令执行工具模块

## 测试配置

运行测试脚本验证配置是否正确：

```bash
python test_config.py
```

## 配置修改

如需修改配置参数，请编辑 `config.py` 文件中的相应变量。修改后，所有使用该配置的模块都会自动使用新的配置值。

## 注意事项

1. 所有路径都使用原始字符串（r前缀）以避免转义字符问题
2. vmrun_path 有备用路径检查机制，如果主路径不存在会自动使用备用路径
3. SSH相关配置提供了默认值，可以在调用时覆盖
4. 所有模块都通过相对路径导入配置，确保在不同环境下都能正常工作

## 文件结构

```
macos_vm/
├── config.py              # 全局配置文件
├── test_config.py         # 配置测试文件
├── CONFIG_README.md       # 配置说明文档
├── web/
│   └── app.py            # Web应用（已更新）
└── py_util/
    ├── main.py           # 主模块（已更新）
    ├── util_vmx.py       # VMX工具（已更新）
    ├── util_ssh.py       # SSH工具（已更新）
    └── util_cmd.py       # 命令工具（已更新）
``` 