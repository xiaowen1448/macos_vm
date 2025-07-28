#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(__file__))

from app import get_vm_online_status, check_ssh_port_open, check_ssh_trust_status, get_vm_ip

def test_strict_online_status():
    """测试严格的在线状态校验逻辑"""
    print("测试严格的在线状态校验逻辑...")
    print("校验条件：IP地址获取成功 + SSH端口开放 + SSH已添加互信")
    
    # 测试虚拟机名称（请根据实际情况修改）
    test_vm_name = "macos10.12"
    
    print(f"\n1. 测试虚拟机: {test_vm_name}")
    
    # 逐步测试每个条件
    print("\n2. 逐步测试校验条件:")
    
    # 条件1：IP地址获取成功
    print("\n   条件1 - IP地址获取:")
    ip = get_vm_ip(test_vm_name)
    if ip:
        print(f"   ✅ IP地址获取成功: {ip}")
        
        # 条件2：SSH端口开放
        print("\n   条件2 - SSH端口开放:")
        ssh_port_open = check_ssh_port_open(ip)
        if ssh_port_open:
            print(f"   ✅ SSH端口开放: {ip}:22")
            
            # 条件3：SSH已添加互信
            print("\n   条件3 - SSH互信状态:")
            ssh_trust = check_ssh_trust_status(ip)
            if ssh_trust:
                print(f"   ✅ SSH互信成功: 可以无密码登录")
            else:
                print(f"   ❌ SSH互信失败: 需要密码登录")
        else:
            print(f"   ❌ SSH端口未开放: {ip}:22")
    else:
        print("   ❌ IP地址获取失败")
    
    # 完整测试
    print("\n3. 完整在线状态测试:")
    online_status = get_vm_online_status(test_vm_name)
    
    print(f"   状态: {online_status['status']}")
    print(f"   原因: {online_status['reason']}")
    print(f"   IP: {online_status['ip']}")
    print(f"   SSH端口开放: {'是' if online_status.get('ssh_port_open', False) else '否'}")
    print(f"   SSH互信: {'是' if online_status['ssh_trust'] else '否'}")
    
    # 状态判断
    if online_status['status'] == 'online':
        print("\n   🎉 虚拟机完全在线！")
        print("   ✅ 满足所有三个条件：")
        print("      - IP地址获取成功")
        print("      - SSH端口开放")
        print("      - SSH已添加互信")
    elif online_status['status'] == 'partial':
        print("\n   ⚠️  虚拟机部分在线")
        print("   ❌ 不满足所有条件，需要进一步配置")
    else:
        print("\n   ❌ 虚拟机离线")
        print("   ❌ 需要检查网络和虚拟机状态")
    
    print("\n测试完成!")

if __name__ == '__main__':
    test_strict_online_status() 