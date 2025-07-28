# 虚拟机批量克隆管理系统

这是一个基于Flask的Web应用，用于批量克隆VMware虚拟机并实时显示执行日志。

## 功能特性

- 🔐 用户登录认证
- 📋 批量克隆虚拟机
- 📸 虚拟机快照功能
- 📊 实时进度显示
- 📝 实时日志推送
- 🎯 任务状态监控
- 📈 克隆统计信息

## 系统要求

- Python 3.7+
- VMware Workstation
- Windows 10/11

## 安装和运行

### 1. 安装依赖

```bash
cd web
pip install -r requirements.txt
```

### 2. 启动应用

```bash
python run_app.py
```

或者直接运行：

```bash
python app.py
```

### 3. 访问系统

打开浏览器访问：http://localhost:5000

- 用户名：admin
- 密码：123456

## 使用说明

### 批量克隆虚拟机

1. 登录系统后，点击左侧菜单的"虚拟机批量克隆"
2. 填写克隆参数：
   - **模板虚拟机**：选择要克隆的模板虚拟机
   - **克隆数量**：要克隆的虚拟机数量（1-20）
   - **目标目录**：克隆后的虚拟机存放目录
   - **命名模式**：虚拟机命名规则（下拉选择或自定义），支持 {timestamp}、{index} 和 {vmname} 占位符
   - **配置文件目录**：选择包含plist文件的目录，系统会自动检查文件数量是否足够
   - **自动启动**：是否在克隆完成后自动启动虚拟机
   - **创建快照**：是否在克隆前为模板虚拟机创建快照备份，并从快照进行克隆
   - **快照命名**：快照命名规则（下拉选择或自定义），支持 {vmname} 和 {timestamp} 占位符

3. 点击"开始克隆"按钮
4. 系统会执行以下流程：
   - 创建虚拟机快照（如果启用）
   - 为每个克隆的虚拟机创建单独的文件夹
   - 从快照进行克隆操作
   - 自动更新vmx文件中的displayName参数
   - 实时显示进度条和执行日志
   - 显示克隆统计信息（成功/失败/运行中/总计）

### 文件夹结构

每个克隆的虚拟机都会创建在独立的文件夹中：

```
D:\macos_vm\NewVM\10.12\
├── VM_20241201_143022_1\
│   ├── VM_20241201_143022_1.vmx
│   ├── VM_20241201_143022_1.vmdk
│   └── ...
├── VM_20241201_143022_2\
│   ├── VM_20241201_143022_2.vmx
│   ├── VM_20241201_143022_2.vmdk
│   └── ...
└── VM_20241201_143022_3\
    ├── VM_20241201_143022_3.vmx
    ├── VM_20241201_143022_3.vmdk
    └── ...
```

### VMX文件更新

系统会自动更新每个克隆虚拟机的vmx文件中的displayName参数：

- **原始值**：`displayName = "Clone of macos10.12"`
- **更新后**：`displayName = "VM_20241201_143022_1"`（使用虚拟机文件夹名称）

### 实时日志功能

- 日志会实时推送到前端页面
- 支持不同级别的日志（info、warning、error、success）
- 可以清空日志或复制日志内容
- 日志包含时间戳和详细信息

### 页面刷新功能

- **自动重新连接**：页面刷新时会自动检查是否有正在运行的任务
- **任务状态保持**：正在运行的任务ID会保存在浏览器localStorage中
- **无缝恢复**：刷新后会自动重新连接到EventSource，继续显示实时日志
- **状态清理**：任务完成后会自动清除localStorage中的任务ID
- **错误处理**：连接错误时会自动清理状态，避免页面卡死

## 目录结构

```
web/
├── app.py                 # 主应用文件
├── requirements.txt       # Python依赖
├── run_app.py           # 启动脚本
├── test_clone.py        # 测试脚本
├── README.md            # 说明文档
└── templates/
    ├── dashboard.html    # 主仪表板
    ├── login.html       # 登录页面
    └── clone_vm.html    # 克隆页面
```

## API接口

### 启动克隆任务

```
POST /api/clone_vm
Content-Type: application/json

{
    "templateVM": "template.vmx",
    "cloneCount": "3",
    "targetDir": "D:\\path\\to\\clones",
    "namingPattern": "VM_{timestamp}_{index}",
    "configPlist": "",
    "autoStart": "false"
}
```

### 获取实时日志

```
GET /api/clone_logs/{task_id}
```

返回Server-Sent Events格式的实时日志流。

## 配置说明

### VMware路径配置

系统会自动检测VMware Workstation的安装路径：
- `C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe`
- `C:\Program Files\VMware\VMware Workstation\vmrun.exe`

### 目录配置

- 模板虚拟机目录：`D:\macos_vm\NewVM\10.12`
- 配置文件目录：`D:\macos_vm\plist`
- 默认克隆目录：`D:\macos_vm\NewVM\cloned_vms`

## 故障排除

### 常见问题

1. **VMware未找到**
   - 确保VMware Workstation已正确安装
   - 检查vmrun.exe是否在默认路径

2. **权限问题**
   - 确保应用有权限访问目标目录
   - 以管理员身份运行应用

3. **克隆失败**
   - 检查模板虚拟机是否存在
   - 确保目标目录有足够空间
   - 查看实时日志了解具体错误

### 日志级别

- **info**：一般信息
- **warning**：警告信息
- **error**：错误信息
- **success**：成功信息

## 开发说明

### 添加新功能

1. 在`app.py`中添加新的路由和功能
2. 在`templates/`目录下创建对应的HTML模板
3. 更新菜单和导航

### 自定义配置

可以修改`app.py`中的以下配置：
- 登录凭据
- 默认目录路径
- VMware路径
- 任务超时时间

## 许可证

本项目仅供学习和研究使用。 