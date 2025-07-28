#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(__file__))

from app import get_vm_online_status, get_vm_ip, check_ssh_trust_status

def test_online_status():
    """测试在线状态功能"""
    print("测试虚拟机在线状态功能...")
    
    # 测试虚拟机名称（请根据实际情况修改）
    test_vm_name = "macos10.12"
    
    print(f"\n1. 测试虚拟机: {test_vm_name}")
    
    # 测试IP获取
    print("\n2. 测试IP获取:")
    ip = get_vm_ip(test_vm_name)
    if ip:
        print(f"   IP地址: {ip}")
        
        # 测试SSH互信状态
        print("\n3. 测试SSH互信状态:")
        ssh_trust = check_ssh_trust_status(ip)
        print(f"   SSH互信状态: {'已设置' if ssh_trust else '未设置'}")
    else:
        print("   无法获取IP地址")
    
    # 测试完整在线状态
    print("\n4. 测试完整在线状态:")
    online_status = get_vm_online_status(test_vm_name)
    print(f"   状态: {online_status['status']}")
    print(f"   原因: {online_status['reason']}")
    print(f"   IP: {online_status['ip']}")
    print(f"   SSH互信: {'是' if online_status['ssh_trust'] else '否'}")
    
    print("\n测试完成!")

if __name__ == '__main__':
    test_online_status() 