# ScptRunner - macOS AppleScript 远程调用工具

## 项目概述

ScptRunner 是一个专为 macOS 10.12 及更高版本设计的应用程序，提供远程 API 来调用和执行 AppleScript (.scpt) 脚本。应用程序使用 Objective-C 编写，确保在 macOS 10.12 上的完全兼容性。

## 功能特性

### 🚀 核心功能
- **HTTP API 服务器**: 在端口 8787 上提供 RESTful API
- **AppleScript 执行**: 通过 `osascript` 执行 .scpt 文件
- **状态栏应用**: 作为状态栏应用运行，不占用 Dock 空间
- **远程调用**: 支持通过 HTTP 请求远程调用脚本

### 📡 API 接口

#### 1. 简化 API (推荐)
```
GET http://localhost:8787/script?name=script_name.scpt
```

**参数:**
- `name`: 脚本文件名（相对于应用程序目录）

**示例:**
```bash
curl "http://localhost:8787/script?name=test_script.scpt"
```

#### 2. 完整路径 API
```
GET http://localhost:8787/run?path=/full/path/to/script.scpt&args=arg1,arg2
```

**参数:**
- `path`: 脚本的完整路径
- `args`: 传递给脚本的参数（可选，逗号分隔）

**示例:**
```bash
curl "http://localhost:8787/run?path=/Users/username/scripts/test.scpt&args=param1,param2"
```

### 📋 响应格式

**成功响应:**
```json
{
  "result": "脚本执行结果"
}
```

**错误响应:**
```json
{
  "error": "错误描述"
}
```

## 系统要求

- **最低系统版本**: macOS 10.12 (Sierra)
- **架构**: x86_64 (Intel)
- **开发工具**: Xcode Command Line Tools

## 构建和安装

### 1. 构建应用程序

```bash
# 给构建脚本执行权限
chmod +x build.sh

# 构建应用程序
./build.sh
```

### 2. 运行应用程序

```bash
# 方法1: 双击运行
open ./ScptRunner.app

# 方法2: 命令行运行
./ScptRunner.app/Contents/MacOS/ScptRunner

# 方法3: 直接运行可执行文件
./ScptRunner.app/Contents/MacOS/ScptRunner
```

## 使用方法

### 1. 启动应用程序
应用程序启动后会在状态栏显示一个图标，表示服务器正在运行。

### 2. 准备脚本文件
将您的 .scpt 文件放在应用程序目录中，或者使用完整路径。

### 3. 调用 API

#### 使用 curl 测试:
```bash
# 测试简化 API
curl "http://localhost:8787/script?name=simple_test.scpt"
curl "http://localhost:8787/script?name=robust_test.scpt"
curl "http://localhost:8787/script?name=test_script.scpt"

# 测试完整路径 API
curl "http://localhost:8787/run?path=/path/to/your/script.scpt"
```

#### 使用提供的测试脚本:
```bash
# 快速测试
chmod +x quick_test.sh
./quick_test.sh

# 详细测试
chmod +x test_api.sh
./test_api.sh

# 调试路径问题
chmod +x debug_paths.sh
./debug_paths.sh
```

#### 使用 Python 测试:
```python
import requests

# 简化 API
response = requests.get("http://localhost:8787/script?name=test_script.scpt")
print(response.json())

# 完整路径 API
response = requests.get("http://localhost:8787/run?path=/path/to/script.scpt")
print(response.json())
```

#### 使用 JavaScript 测试:
```javascript
// 简化 API
fetch("http://localhost:8787/script?name=test_script.scpt")
  .then(response => response.json())
  .then(data => console.log(data));

// 完整路径 API
fetch("http://localhost:8787/run?path=/path/to/script.scpt")
  .then(response => response.json())
  .then(data => console.log(data));
```

## 状态栏菜单

应用程序在状态栏提供以下功能：

- **服务器状态**: 显示服务器运行状态和端口
- **测试 API**: 测试当前 API 连接
- **打开应用文件夹**: 打开应用程序所在目录
- **退出**: 退出应用程序

## 项目结构

```
ScptRunner/
├── Sources/
│   └── main.m              # 主要源代码
├── Info.plist              # 应用程序配置
├── build.sh                # 构建脚本
├── test_script.scpt        # 测试脚本
├── simple_test.scpt        # 简单测试脚本
├── robust_test.scpt        # 健壮测试脚本
├── README.md               # 项目说明
└── ScptRunner.app/         # 构建输出
```

## 技术实现

### 🔧 核心技术
- **语言**: Objective-C
- **框架**: AppKit, Foundation, CoreFoundation
- **网络**: BSD Sockets (HTTP 服务器)
- **脚本执行**: NSTask + osascript
- **UI**: 状态栏应用 (NSStatusItem)

### 🛡️ 兼容性特性
- 使用传统的 Objective-C 语法
- 避免使用 macOS 10.13+ 的 API
- 使用 BSD Sockets 而不是 Network framework
- 设置 `NSApplicationActivationPolicyAccessory` 确保状态栏兼容性

## 故障排除

### 常见问题

1. **应用程序无法启动**
   - 检查是否在 macOS 10.12 或更高版本
   - 确保有执行权限: `chmod +x build.sh`

2. **API 调用失败**
   - 确认应用程序正在运行
   - 检查端口 8787 是否被占用
   - 验证脚本文件路径和权限

3. **脚本执行失败**
   - 确认脚本文件存在且可读
   - 检查脚本语法是否正确
   - 验证脚本权限设置
   - 确保脚本文件在正确位置（应用程序目录、当前目录或桌面）

4. **"Script file not found" 错误**
   - 运行 `./debug_paths.sh` 检查文件路径
   - 确保 `test_script.scpt` 在应用程序目录中
   - 或者将脚本放在桌面或当前工作目录

### 调试方法

1. **查看控制台日志**
   ```bash
   Console.app
   ```

2. **直接运行可执行文件**
   ```bash
   ./ScptRunner.app/Contents/MacOS/ScptRunner
   ```

3. **检查网络连接**
   ```bash
   netstat -an | grep 8787
   ```

## 许可证

本项目遵循 MIT 许可证。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目。

---

**注意**: 此应用程序专为 macOS 10.12 设计，确保在较新的 macOS 版本上也能正常运行。 