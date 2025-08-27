#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
macOS 虚拟机管理系统 - PyInstaller 打包脚本

此脚本用于将 Flask 应用和 PyQt5 WebView 应用打包为独立的 Windows 可执行文件

使用方法:
    python build_exe.py

生成的文件:
    - dist/macos_vm_web.exe (Web版本)
    - dist/macos_vm_desktop.exe (桌面版本)
    - dist/macos_vm_service.exe (服务版本)
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / 'dist'
BUILD_DIR = PROJECT_ROOT / 'build'

# PyInstaller 配置
PYINSTALLER_OPTIONS = [
    '--clean',
    '--noconfirm',
    '--onedir',  # 使用单目录模式，便于包含资源文件
    '--windowed',  # Windows 下隐藏控制台窗口
    '--add-data', f'{PROJECT_ROOT}/web;web',
    '--add-data', f'{PROJECT_ROOT}/config.py;.',
    '--add-data', f'{PROJECT_ROOT}/macos_script;macos_script',
    '--hidden-import', 'flask',
    '--hidden-import', 'PyQt5',
    '--hidden-import', 'PyQt5.QtCore',
    '--hidden-import', 'PyQt5.QtWidgets',
    '--hidden-import', 'PyQt5.QtWebEngineWidgets',
    '--hidden-import', 'paramiko',
    '--hidden-import', 'requests',
    '--hidden-import', 'psutil',
    '--hidden-import', 'watchdog',
]

def clean_build_dirs():
    """清理构建目录"""
    print("🧹 清理构建目录...")
    for dir_path in [DIST_DIR, BUILD_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"   已删除: {dir_path}")

def check_dependencies():
    """检查必要的依赖包"""
    print("📦 检查依赖包...")
    required_packages = [
        'pyinstaller',
        'flask',
        'PyQt5',
        'PyQtWebEngine',
        'paramiko',
        'requests',
        'psutil',
        'watchdog'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.lower().replace('-', '_'))
            print(f"   ✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"   ❌ {package} (缺失)")
    
    if missing_packages:
        print(f"\n⚠️  缺失依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    return True

def create_spec_file(app_name, entry_point, icon_path=None):
    """创建 PyInstaller spec 文件"""
    spec_content = f"""
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['{entry_point}'],
    pathex=['{PROJECT_ROOT}'],
    binaries=[],
    datas=[
        ('{PROJECT_ROOT}/web', 'web'),
        ('{PROJECT_ROOT}/config.py', '.'),
        ('{PROJECT_ROOT}/macos_script', 'macos_script'),
    ],
    hiddenimports=[
        'flask',
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtWidgets', 
        'PyQt5.QtWebEngineWidgets',
        'paramiko',
        'requests',
        'psutil',
        'watchdog',
        'engineio.async_drivers.threading',
        'socketio.async_drivers.threading',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='{app_name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    {'icon="' + str(icon_path) + '",' if icon_path else ''}
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='{app_name}',
)
"""
    
    spec_file = PROJECT_ROOT / f'{app_name}.spec'
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    return spec_file

def build_app(app_name, entry_point, description):
    """构建单个应用"""
    print(f"\n🔨 构建 {description}...")
    
    # 创建 spec 文件
    spec_file = create_spec_file(app_name, entry_point)
    
    try:
        # 运行 PyInstaller
        cmd = ['pyinstaller', str(spec_file)]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
        
        if result.returncode == 0:
            print(f"   ✅ {description} 构建成功")
            print(f"   📁 输出目录: {DIST_DIR / app_name}")
            return True
        else:
            print(f"   ❌ {description} 构建失败")
            print(f"   错误信息: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"   ❌ 构建过程中出现异常: {e}")
        return False
    finally:
        # 清理 spec 文件
        if spec_file.exists():
            spec_file.unlink()

def copy_additional_files():
    """复制额外的文件到输出目录"""
    print("\n📋 复制额外文件...")
    
    additional_files = [
        ('README.md', 'README.md'),
        ('requirements.txt', 'requirements.txt'),
        ('config.py', 'config_template.py'),
    ]
    
    for app_dir in DIST_DIR.glob('macos_vm_*'):
        if app_dir.is_dir():
            print(f"   📁 处理目录: {app_dir.name}")
            
            for src_file, dst_file in additional_files:
                src_path = PROJECT_ROOT / src_file
                dst_path = app_dir / dst_file
                
                if src_path.exists():
                    shutil.copy2(src_path, dst_path)
                    print(f"      ✅ 复制: {src_file} -> {dst_file}")
                else:
                    print(f"      ⚠️  文件不存在: {src_file}")
            
            # 创建日志目录
            logs_dir = app_dir / 'logs'
            logs_dir.mkdir(exist_ok=True)
            print(f"      📁 创建日志目录: logs")
            
            # 创建启动脚本
            create_launcher_script(app_dir)

def create_launcher_script(app_dir):
    """为每个应用创建启动脚本"""
    app_name = app_dir.name
    exe_name = f"{app_name}.exe"
    
    launcher_content = f"""@echo off
chcp 65001 >nul
echo ========================================
echo   macOS 虚拟机管理系统
echo   {app_name}
echo ========================================
echo.

cd /d "%~dp0"

echo 正在启动应用...
start "" "{exe_name}"

echo 应用已启动！
echo.
echo 如需停止应用，请关闭相应窗口或进程。
echo.
pause
"""
    
    launcher_path = app_dir / f"启动_{app_name}.bat"
    with open(launcher_path, 'w', encoding='gbk') as f:
        f.write(launcher_content)
    
    print(f"      📜 创建启动脚本: 启动_{app_name}.bat")

def create_readme_for_dist():
    """为发布版本创建说明文件"""
    print("\n📄 创建发布说明文件...")
    
    readme_content = """
# macOS 虚拟机管理系统 - 发布版本

## 包含的应用

### 1. macos_vm_web
Web 浏览器版本，通过浏览器访问管理界面。
- 运行: 双击 `macos_vm_web.exe` 或 `启动_macos_vm_web.bat`
- 访问: http://localhost:5000
- 默认账号: admin / 123456

### 2. macos_vm_desktop  
桌面应用版本，集成了 Web 界面的桌面应用。
- 运行: 双击 `macos_vm_desktop.exe` 或 `启动_macos_vm_desktop.bat`
- 无需浏览器，直接显示管理界面

### 3. macos_vm_service
后台服务版本，可以作为 Windows 服务运行。
- 运行: 双击 `macos_vm_service.exe` 或 `启动_macos_vm_service.bat`
- 后台运行，通过浏览器访问 http://localhost:5000

## 使用前准备

1. **配置文件**: 首次运行前，请根据您的环境修改 `config_template.py` 并重命名为 `config.py`

2. **VMware 环境**: 确保已安装 VMware Workstation Pro 或 Player

3. **模板虚拟机**: 准备好 macOS 模板虚拟机文件

4. **目录权限**: 确保应用对相关目录有读写权限

## 故障排除

- 如果应用无法启动，请检查 `logs` 目录中的日志文件
- 确保防火墙允许应用访问网络
- 检查 VMware 相关路径配置是否正确

## 技术支持

- Telegram: @xiaowen1448
- WeChat: w8686512

---
生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    readme_path = DIST_DIR / 'README_发布版本.txt'
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"   ✅ 创建: {readme_path}")

def main():
    """主函数"""
    print("🚀 macOS 虚拟机管理系统 - PyInstaller 打包工具")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 清理构建目录
    clean_build_dirs()
    
    # 构建应用列表
    apps_to_build = [
        ('macos_vm_web', 'app.py', 'Web 浏览器版本'),
        ('macos_vm_desktop', 'webview_app.py', '桌面应用版本'),
        ('macos_vm_service', 'service_runner.py', '后台服务版本'),
    ]
    
    # 构建每个应用
    success_count = 0
    for app_name, entry_point, description in apps_to_build:
        if build_app(app_name, entry_point, description):
            success_count += 1
    
    # 复制额外文件
    if success_count > 0:
        copy_additional_files()
        create_readme_for_dist()
    
    # 构建结果总结
    print("\n" + "=" * 60)
    print(f"📊 构建完成: {success_count}/{len(apps_to_build)} 个应用构建成功")
    
    if success_count > 0:
        print(f"\n📁 输出目录: {DIST_DIR}")
        print("\n🎉 可执行文件已生成，可以分发使用！")
        
        # 显示生成的文件
        print("\n📦 生成的应用:")
        for app_dir in sorted(DIST_DIR.glob('macos_vm_*')):
            if app_dir.is_dir():
                exe_file = app_dir / f"{app_dir.name}.exe"
                if exe_file.exists():
                    size_mb = exe_file.stat().st_size / (1024 * 1024)
                    print(f"   📱 {app_dir.name}.exe ({size_mb:.1f} MB)")
    else:
        print("\n❌ 没有应用构建成功，请检查错误信息")
        sys.exit(1)

if __name__ == '__main__':
    main()