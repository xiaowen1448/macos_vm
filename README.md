# macOS 虚拟机批量克隆管理系统

## 项目简介

macOS 虚拟机批量克隆管理系统是一个基于 Flask 和 PyQt5 的综合性虚拟机管理平台，专门用于 macOS 虚拟机的批量克隆、配置管理和自动化运维。系统提供了 Web 界面和桌面应用两种访问方式，支持虚拟机的批量创建、五码配置、Apple ID 管理、脚本执行等功能。

## 系统截图

### 新版控制台开发登录窗口
<img width="1841" height="972" alt="image" src="https://github.com/user-attachments/assets/4b99351c-f044-488d-91cb-23ab8eee3e67" />

<img width="1841" height="972" alt="image" src="https://github.com/user-attachments/assets/71ff203e-d53c-421c-a6c6-80e2908558fc" />

### 虚拟机批量克隆，实时和历史日志信息
<img width="1841" height="972" alt="image" src="https://github.com/user-attachments/assets/1c196730-be99-4f26-8d1c-d22b86619d58" />

### 虚拟机管理界面，增加图标状态监控，开机关机，重启挂起，脚本发送和脚本执行按钮
<img width="1841" height="972" alt="image" src="https://github.com/user-attachments/assets/efa1175c-8f4f-4b99-8b9c-75fda0580918" />

### 虚拟机脚本管理
<img width="1841" height="972" alt="image" src="https://github.com/user-attachments/assets/f3f3ab8a-2658-4fde-877f-1015fcbb6188" />

### 虚拟机五码管理
<img width="1841" height="972" alt="image" src="https://github.com/user-attachments/assets/55ba27c1-7551-48ac-9a38-08dd8fdbfa4b" />

## 主要功能

### 🖥️ 虚拟机管理
- **批量克隆**: 支持从模板虚拟机批量克隆多个实例
- **自动配置**: 克隆完成后自动配置五码和 JU 值
- **状态监控**: 实时监控虚拟机运行状态和网络连通性
- **快照管理**: 支持虚拟机快照的创建和管理
- **电源管理**: 支持开机、关机、重启、挂起等操作

### 🔧 配置管理
- **五码配置**: 批量管理和应用五码配置文件，确保每台虚拟机五码唯一
- **JU值管理**: 自动生成和配置唯一的 kbjfrfpoJU 值
- **Apple ID 管理**: Apple ID 的批量导入、分配和状态跟踪
- **手机号管理**: 发信手机号的管理和分配
- **配置文件解析**: 支持 JSON 和 plist 格式的配置文件解析

### 📜 脚本管理
- **脚本上传**: 支持 .sh 和 .scpt 脚本文件的上传和管理
- **批量执行**: 支持在多个虚拟机上批量执行脚本
- **执行日志**: 详细的脚本执行日志和结果反馈
- **远程执行**: 通过 SSH 连接远程执行脚本

### 📊 系统监控
- **实时日志**: 实时显示系统操作日志
- **任务进度**: 可视化的任务执行进度显示
- **状态指示**: 直观的虚拟机状态指示器
- **历史记录**: 完整的操作历史记录

## 系统架构

```
项目根目录/
├── app.py                 # Flask 主应用
├── webview_app.py         # PyQt5 桌面应用
├── config.py              # 全局配置文件
├── requirements.txt       # Python 依赖包
├── start.bat             # Web 版启动脚本
├── start_webview.bat     # 桌面版启动脚本
├── build_exe.py          # 打包为 exe 的脚本
├── service_runner.py     # 后台服务运行器
├── web/                  # Web 资源目录
│   └── templates/        # HTML 模板文件
├── logs/                 # 日志文件目录
├── macos_script/         # macOS 脚本文件
│   ├── macos_sh/        # Shell 脚本
│   └── macos_scpt/      # AppleScript 脚本
└── vm_util/             # 虚拟机工具和配置
```

## 环境要求

### 系统要求
- **操作系统**: Windows 10/11 (64位)
- **Python**: 3.7 或更高版本
- **VMware**: VMware Workstation Pro 15+ 或 VMware Workstation Player

### VMware 环境配置
推荐使用 VMware® Workstation 17 Pro (17.5.1 build-23298084)

### 硬件要求
- **内存**: 建议 16GB 以上 (每个 macOS 虚拟机需要 4-8GB)
- **存储**: 建议 500GB 以上可用空间
- **CPU**: 支持虚拟化的多核处理器

## 安装指南

### 1. 克隆项目
```bash
git clone <repository-url>
cd macos_vm
```

### 2. 安装 Python 依赖
```bash
pip install -r requirements.txt
```

### 3. 配置系统
编辑 `config.py` 文件，根据您的环境修改以下配置：

```python
# 模板虚拟机路径
template_dir = r'D:\macos_vm\TemplateVM'

# 虚拟机克隆目录
clone_dir = r'D:\macos_vm\NewVM\10.12_clone'

# vmrun 运行路径
vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'

# 用户认证信息
USERNAME = 'admin'
PASSWORD = '123456'
```

### 4. 准备模板虚拟机
- 在 `template_dir` 目录下放置您的 macOS 模板虚拟机
- 确保模板虚拟机已正确配置并可以正常启动
- 支持 macOS 10.12 及更高版本

## 使用方法

### 启动方式

#### 1. Web 浏览器版本
```bash
# 方法1: 使用批处理文件
start.bat

# 方法2: 直接运行 Python
python app.py
```

访问 http://localhost:5000
- 默认用户名: admin
- 默认密码: 123456

#### 2. 桌面应用版本 (WebView)
```bash
# 方法1: 使用批处理文件
start_webview.bat

# 方法2: 直接运行 Python
python webview_app.py
```

#### 3. 后台服务版本
```bash
# 以 Windows 服务方式运行
python service_runner.py
```

#### 4. 打包为 exe 文件
```bash
# 生成独立的 exe 文件
python build_exe.py
```

### 主要操作流程

#### 1. 批量克隆虚拟机
1. 登录系统后，进入「虚拟机批量克隆」页面
2. 选择模板虚拟机和克隆数量
3. 配置克隆参数（目录、命名规则等）
4. 选择五码配置文件
5. 点击「开始克隆」，系统将自动完成克隆和配置
6. 系统会自动为每台虚拟机生成唯一的 JU 值和五码

#### 2. JU 值查看和验证
使用 iMessageDebug 工具查看 JU 值：
```bash
/Users/wx/Desktop/iMessageDebug
```

输出示例：
```
**********************iMessage Debug**********************
Model: VMware20,1
Board-id: Mac-AA95B1DDAB278B95
SerialNumber: VMLbH9Kbb8Q4
Hardware UUID: 564D9976-62CB-847F-619E-157CB36A4660

kbjfrfpoJU: 39feee3569700187b9e15f700427984e20
```

#### 3. 管理配置文件
1. 进入相应的管理页面（五码管理、Apple ID 管理等）
2. 上传或编辑配置文件
3. 查看配置文件的使用状态
4. 批量应用配置到虚拟机

#### 4. 执行脚本
1. 进入「虚拟机脚本管理」页面
2. 上传脚本文件（.sh 或 .scpt）
3. 选择目标虚拟机
4. 执行脚本并查看结果

## 配置说明

### 目录结构配置
系统使用多个目录来组织不同类型的文件：

- `template_dir`: 模板虚拟机存放目录
- `clone_dir`: 克隆虚拟机输出目录
- `vm_chengpin_dir`: 成品虚拟机目录
- `script_upload_dirs`: 脚本文件目录（支持多个）
- `wuma_config_dir`: 五码配置文件目录
- `appleid_unused_dir`: 未使用的 Apple ID 目录

### 网络配置
系统默认监听 `localhost:5000`，如需外部访问，请修改 `app.py` 中的 host 配置。

### 虚拟机配置
- `vm_username`: macOS 虚拟机用户名
- `vm_password`: macOS 虚拟机密码
- `script_remote_path`: 脚本在虚拟机中的存放路径

## 日志系统

系统提供详细的日志记录功能：

- **应用日志**: `logs/app_debug_YYYY-MM-DD.log`
- **WebView 日志**: `logs/webview_debug_YYYY-MM-DD.log`
- **实时日志**: Web 界面中的实时日志显示

日志级别包括：DEBUG、INFO、WARNING、ERROR

## 故障排除

### 常见问题

1. **虚拟机克隆失败**
   - 检查 VMware 是否正确安装
   - 确认 vmrun.exe 路径配置正确
   - 检查模板虚拟机是否存在且可访问
   - 确保有足够的磁盘空间

2. **网络连接问题**
   - 确认虚拟机网络配置正确
   - 检查防火墙设置
   - 验证 SSH 密钥配置

3. **脚本执行失败**
   - 检查脚本文件权限
   - 确认虚拟机中的脚本路径存在
   - 查看详细的执行日志

4. **JU 值重复问题**
   - 确保每次克隆都使用不同的配置文件
   - 检查五码配置文件是否正确
   - 验证克隆过程是否完整

### 调试模式
系统默认启用调试模式，详细日志会记录在 logs 目录中。

## 安全注意事项

1. **修改默认密码**: 部署前请修改 `config.py` 中的默认用户名和密码
2. **网络访问控制**: 如需外部访问，请配置适当的防火墙规则
3. **文件权限**: 确保敏感配置文件的访问权限设置正确
4. **定期备份**: 定期备份重要的配置文件和虚拟机模板

## 打包部署

### 生成 exe 文件
系统提供了自动打包脚本，可以将整个应用打包为独立的 exe 文件：

```bash
python build_exe.py
```

生成的 exe 文件包含：
- 完整的 Python 运行环境
- 所有依赖库
- Web 资源文件
- 配置文件模板

### 后台服务运行
支持以 Windows 服务方式运行：

```bash
# 安装服务
python service_runner.py install

# 启动服务
python service_runner.py start

# 停止服务
python service_runner.py stop

# 卸载服务
python service_runner.py remove
```

## 开发信息

### 技术栈
- **后端**: Flask (Python Web 框架)
- **前端**: HTML5 + CSS3 + JavaScript + Bootstrap
- **桌面应用**: PyQt5 + QWebEngine
- **虚拟机管理**: VMware vmrun 命令行工具
- **远程连接**: Paramiko (SSH 客户端)
- **进程管理**: psutil
- **文件监控**: watchdog
- **打包工具**: PyInstaller

### 扩展开发
系统采用模块化设计，支持功能扩展：

1. **添加新的管理模块**: 在 `web/templates/` 中添加新的 HTML 模板
2. **扩展 API 接口**: 在 `app.py` 中添加新的路由处理函数
3. **自定义脚本**: 在 `macos_script/` 目录中添加自定义脚本
4. **插件开发**: 支持第三方插件扩展

## 版本更新

### 最新功能
- ✅ 新版控制台登录界面
- ✅ 虚拟机状态实时监控
- ✅ 批量脚本执行功能
- ✅ 五码配置管理
- ✅ Apple ID 管理系统
- ✅ 支持 macOS 10.12 低版本克隆
- ✅ WebView 桌面应用
- ✅ 后台服务运行模式
- ✅ exe 打包部署

## 技术支持

如遇到问题或有改进建议，请通过以下方式联系：

- **Telegram**: @xiaowen1448
- **WeChat**: w8686512
- **提交 Issue**: 在项目仓库中提交问题报告
- **查看文档**: 参考项目文档和示例

## 许可证

本项目采用 MIT 许可证，详情请参阅 LICENSE 文件。

---

**注意**: 本系统仅供学习和研究使用，请遵守相关法律法规和软件许可协议。使用本系统进行虚拟机克隆时，请确保拥有相应的软件许可证。







