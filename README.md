# macOS 虚拟机管理系统

<div align="center">

![macOS VM Manager](https://img.shields.io/badge/macOS-VM%20Manager-blue?style=for-the-badge&logo=apple)
![Python](https://img.shields.io/badge/Python-3.7+-green?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-Web%20Framework-red?style=for-the-badge&logo=flask)
![PyQt5](https://img.shields.io/badge/PyQt5-Desktop%20App-orange?style=for-the-badge&logo=qt)

**一个功能强大的 macOS 虚拟机管理和自动化系统**

支持虚拟机批量管理、iMessage 自动化、AppleID 管理等功能

</div>

## 📋 目录

- [功能特性](#-功能特性)
- [系统架构](#-系统架构)
- [环境要求](#-环境要求)
- [快速开始](#-快速开始)
- [部署方式](#-部署方式)
- [配置说明](#-配置说明)
- [使用指南](#-使用指南)
- [API 文档](#-api-文档)
- [故障排除](#-故障排除)
- [开发指南](#-开发指南)
- [更新日志](#-更新日志)
- [许可证](#-许可证)

## 🚀 功能特性

### 核心功能
- **🖥️ 虚拟机管理**: 批量创建、启动、停止、克隆 macOS 虚拟机
- **📱 iMessage 自动化**: 自动登录、消息发送、蓝号检测
- **🆔 AppleID 管理**: 批量管理 AppleID 账户和验证
- **📞 号码管理**: 手机号码批量导入和状态管理
- **🔄 自动化脚本**: 支持 AppleScript 和 Shell 脚本执行
- **📊 实时监控**: 虚拟机状态监控和日志查看

### 界面支持
- **🌐 Web 管理界面**: 基于 Flask 的现代化 Web 界面
- **🖥️ 桌面应用**: 基于 PyQt5 的原生桌面应用
- **⚙️ Windows 服务**: 支持后台服务模式运行

### 高级特性
- **🔧 批量操作**: 支持虚拟机批量克隆和配置
- **📝 日志系统**: 完整的操作日志和错误追踪
- **🔒 安全认证**: 用户登录和权限管理
- **📦 一键打包**: 支持打包为 Windows 可执行文件

## 🏗️ 系统架构

```
macOS VM Manager
├── Web 层 (Flask)
│   ├── 用户界面 (HTML/CSS/JS)
│   ├── API 接口 (RESTful)
│   └── 认证系统
├── 应用层 (Python)
│   ├── 虚拟机控制器
│   ├── iMessage 自动化
│   ├── AppleID 管理器
│   └── 脚本执行引擎
├── 数据层
│   ├── 配置文件 (JSON/YAML)
│   ├── 日志文件
│   └── 临时数据
└── 系统层
    ├── VMware 集成
    ├── SSH 连接
    └── 文件系统操作
```

## 💻 环境要求

### 基础环境
- **操作系统**: Windows 10/11 (推荐)
- **Python**: 3.7 或更高版本
- **VMware**: VMware Workstation Pro 15+ 或 VMware Player
- **内存**: 8GB+ (推荐 16GB+)
- **存储**: 100GB+ 可用空间

### Python 依赖
主要依赖包将通过 `requirements.txt` 自动安装：
- Flask 2.0+ (Web 框架)
- PyQt5 5.15+ (桌面界面)
- paramiko 2.7+ (SSH 连接)
- psutil 5.8+ (系统监控)
- requests 2.25+ (HTTP 请求)

## 🚀 快速开始

### 1. 克隆项目
```bash
git clone <repository-url>
cd macos_vm
```

### 2. 安装依赖
```bash
# 自动安装 (推荐)
python -m pip install -r requirements.txt

# 或手动安装核心依赖
pip install flask PyQt5 paramiko psutil requests
```

### 3. 配置系统
```bash
# 复制配置模板
cp config.py.example config.py

# 编辑配置文件
notepad config.py
```

### 4. 启动应用

#### Web 版本 (推荐)
```bash
# Windows
start.bat

# 或直接运行
python app.py
```

#### 桌面版本
```bash
# Windows
start_webview.bat

# 或直接运行
python webview_app.py
```

## 📦 部署方式

### 方式一: 开发模式
直接运行 Python 脚本，适合开发和测试：
```bash
python app.py          # Web 版本
python webview_app.py  # 桌面版本
```

### 方式二: 打包部署
使用内置打包脚本生成可执行文件：
```bash
python build_exe.py
```
生成的文件位于 `dist/` 目录：
- `macos_vm_web/` - Web 浏览器版本
- `macos_vm_desktop/` - 桌面应用版本
- `macos_vm_service/` - 后台服务版本

### 方式三: Windows 服务
安装为 Windows 系统服务：
```bash
# 安装服务
python service_runner.py install

# 启动服务
python service_runner.py start

# 查看状态
python service_runner.py status
```

## ⚙️ 配置说明

### 主配置文件 (config.py)
```python
# 基础配置
DEBUG = False
SECRET_KEY = 'your-secret-key'
HOST = '0.0.0.0'
PORT = 5000

# 虚拟机配置
VM_BASE_PATH = 'D:/VMs/macOS'
VM_TEMPLATE_PATH = 'D:/VMs/Templates'
SSH_USERNAME = 'admin'
SSH_PASSWORD = 'password'

# 日志配置
LOG_LEVEL = 'INFO'
LOG_FILE = 'logs/app.log'
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
```

### 虚拟机模板配置
在 `vm_util/plist/` 目录下配置虚拟机模板：
- 硬件配置 (CPU、内存、磁盘)
- 网络设置
- 序列号和硬件标识

## 📖 使用指南

### Web 界面使用
1. **登录系统**: 默认用户名 `admin`，密码 `123456`
2. **虚拟机管理**: 创建、启动、停止、克隆虚拟机
3. **iMessage 自动化**: 配置 AppleID，执行消息发送任务
4. **监控面板**: 查看系统状态和操作日志

### 桌面应用使用
- 启动后自动打开管理界面
- 支持系统托盘最小化
- 提供快捷操作菜单

### 命令行工具
```bash
# 虚拟机操作
python -m vm_util.py_util.main --action start --vm-name "macOS-01"
python -m vm_util.py_util.main --action clone --template "base" --count 5

# 脚本执行
python -m macos_script.executor --script "login.scpt" --vm "macOS-01"
```

## 🔧 API 文档

### 认证接口
```http
POST /api/login
Content-Type: application/json

{
  "username": "admin",
  "password": "123456"
}
```

### 虚拟机管理
```http
# 获取虚拟机列表
GET /api/vms

# 启动虚拟机
POST /api/vms/{vm_id}/start

# 停止虚拟机
POST /api/vms/{vm_id}/stop

# 克隆虚拟机
POST /api/vms/clone
Content-Type: application/json

{
  "template": "base-template",
  "count": 3,
  "prefix": "macOS"
}
```

### iMessage 自动化
```http
# 发送消息
POST /api/imessage/send
Content-Type: application/json

{
  "vm_id": "macOS-01",
  "phone_number": "+1234567890",
  "message": "Hello World"
}
```

## 🛠️ 故障排除

### 常见问题

#### 1. Python 环境问题
```bash
# 检查 Python 版本
python --version

# 升级 pip
python -m pip install --upgrade pip

# 重新安装依赖
pip install -r requirements.txt --force-reinstall
```

#### 2. 虚拟机连接失败
- 检查 VMware 是否正常运行
- 确认虚拟机 SSH 服务已启动
- 验证网络连接和防火墙设置

#### 3. PyQt5 安装失败
```bash
# Windows 用户
pip install PyQt5 PyQtWebEngine --index-url https://pypi.douban.com/simple/

# 或使用 conda
conda install pyqt
```

#### 4. 权限问题
- 以管理员身份运行命令提示符
- 检查文件和目录权限
- 确保 VMware 有足够权限

### 日志查看
```bash
# 查看应用日志
tail -f logs/app.log

# 查看虚拟机日志
tail -f logs/vm_operations.log

# 查看错误日志
tail -f logs/error.log
```

## 👨‍💻 开发指南

### 项目结构
```
macos_vm/
├── app.py                 # Flask Web 应用入口
├── webview_app.py         # PyQt5 桌面应用入口
├── config.py              # 配置文件
├── requirements.txt       # Python 依赖
├── build_exe.py          # 打包脚本
├── service_runner.py     # Windows 服务
├── web/                  # Web 界面文件
│   └── templates/        # HTML 模板
├── vm_util/              # 虚拟机工具
│   ├── py_util/         # Python 工具脚本
│   ├── bat/             # 批处理脚本
│   └── plist/           # 配置文件
├── macos_script/         # macOS 脚本
│   ├── macos_scpt/      # AppleScript 脚本
│   └── macos_sh/        # Shell 脚本
└── logs/                 # 日志文件
```

### 开发环境设置
```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 安装开发依赖
pip install -r requirements.txt
pip install flake8 pytest  # 开发工具
```

### 代码规范
- 使用 PEP 8 代码风格
- 函数和类添加文档字符串
- 使用类型提示 (Type Hints)
- 编写单元测试

### 测试
```bash
# 运行测试
pytest tests/

# 代码检查
flake8 .

# 类型检查
mypy .
```

## 📝 更新日志

### v2.0.0 (2024-01-XX)
- ✨ 新增桌面应用支持 (PyQt5)
- ✨ 新增 Windows 服务模式
- ✨ 新增一键打包功能
- 🔧 优化启动脚本和错误处理
- 📚 完善文档和使用指南

### v1.5.0 (2023-XX-XX)
- ✨ 新增 iMessage 自动化功能
- ✨ 新增批量虚拟机克隆
- 🔧 改进日志系统
- 🐛 修复若干已知问题

### v1.0.0 (2023-XX-XX)
- 🎉 初始版本发布
- ✨ 基础虚拟机管理功能
- ✨ Web 管理界面
- ✨ AppleID 管理功能

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📞 技术支持

- **问题反馈**: 请在 GitHub Issues 中提交
- **功能建议**: 欢迎在 Issues 中讨论
- **文档问题**: 请提交 PR 或 Issue

## ⚠️ 免责声明

本软件仅供学习和研究使用，请遵守相关法律法规。使用本软件所产生的任何后果由使用者自行承担。

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐ Star 支持一下！**

 Made with ❤️ by macOS VM Manager Team

</div>