#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import datetime

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import get_vm_online_status, get_vm_status, get_vm_ip, find_vm_file

def test_vm_status(vm_name):
    """测试虚拟机状态检测"""
    print(f"\n=== 测试虚拟机状态检测: {vm_name} ===")
    
    # 1. 查找虚拟机文件
    print("\n1. 查找虚拟机文件...")
    vm_file = find_vm_file(vm_name)
    if vm_file:
        print(f"   找到虚拟机文件: {vm_file}")
    else:
        print(f"   未找到虚拟机文件: {vm_name}")
        return
    
    # 2. 检测虚拟机状态
    print("\n2. 检测虚拟机状态...")
    vm_status = get_vm_status(vm_file)
    print(f"   虚拟机状态: {vm_status}")
    
    # 3. 获取IP地址
    print("\n3. 获取IP地址...")
    vm_ip = get_vm_ip(vm_name)
    if vm_ip:
        print(f"   获取到IP地址: {vm_ip}")
    else:
        print(f"   无法获取IP地址")
        return
    
    # 4. 检查在线状态
    print("\n4. 检查在线状态...")
    online_status = get_vm_online_status(vm_name)
    print(f"   在线状态结果: {online_status}")
    
    return online_status

def main():
    """主函数"""
    print("=== 虚拟机状态调试工具 ===")
    
    # 获取命令行参数
    if len(sys.argv) < 2:
        print("使用方法: python debug_vm_status.py <虚拟机名称>")
        print("示例: python debug_vm_status.py VM_20250729_102224_12")
        return
    
    vm_name = sys.argv[1]
    result = test_vm_status(vm_name)
    
    if result:
        print(f"\n=== 最终结果 ===")
        print(f"虚拟机名称: {vm_name}")
        print(f"状态: {result.get('status', 'unknown')}")
        print(f"原因: {result.get('reason', 'unknown')}")
        print(f"IP地址: {result.get('ip', 'unknown')}")
        print(f"SSH端口开放: {result.get('ssh_port_open', False)}")
        print(f"SSH互信: {result.get('ssh_trust', False)}")
        print(f"虚拟机状态: {result.get('vm_status', 'unknown')}")

if __name__ == "__main__":
    main() 