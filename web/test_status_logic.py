#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def test_status_logic():
    """测试状态判断逻辑"""
    print("=== 测试状态判断逻辑 ===")
    
    # 模拟三个条件都满足的情况
    ip_status = {'success': True}
    ssh_port_open = True
    ssh_trust_status = True
    vm_status = 'unknown'
    
    print(f"IP状态: {ip_status}")
    print(f"SSH端口开放: {ssh_port_open}")
    print(f"SSH互信: {ssh_trust_status}")
    print(f"虚拟机状态: {vm_status}")
    
    # 计算条件满足情况
    conditions_met = 0
    total_conditions = 3
    
    if ip_status['success']:
        conditions_met += 1
    if ssh_port_open:
        conditions_met += 1
    if ssh_trust_status:
        conditions_met += 1
    
    print(f"条件满足情况: {conditions_met}/{total_conditions}")
    
    if conditions_met == total_conditions:
        print("三个条件都满足，应该返回online状态")
        status_text = '完全在线'
        reason_text = 'IP可达 + SSH端口开放 + SSH互信成功'
        if vm_status == 'unknown':
            status_text = '完全在线（状态未知）'
            reason_text = 'IP可达 + SSH端口开放 + SSH互信成功（虚拟机状态未知）'
        
        result = {
            'status': 'online',
            'reason': reason_text,
            'ip': '192.168.1.100',
            'ssh_trust': True,
            'ssh_port_open': True,
            'vm_status': vm_status
        }
        print(f"返回结果: {result}")
        return result
    else:
        print("条件不满足")
        return None

if __name__ == "__main__":
    test_status_logic() 