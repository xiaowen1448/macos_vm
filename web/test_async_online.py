#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time

def test_async_online_status():
    """测试异步在线状态获取功能"""
    print("测试异步在线状态获取功能...")
    
    # 测试数据
    test_vm_names = ["macos10.12", "macos10.15", "test_vm"]
    
    print(f"\n1. 测试虚拟机列表: {test_vm_names}")
    
    # 模拟API调用
    url = "http://127.0.0.1:5000/api/vm_online_status"
    data = {
        "vm_names": test_vm_names
    }
    
    try:
        print("\n2. 发送异步获取请求...")
        start_time = time.time()
        
        response = requests.post(url, json=data, timeout=30)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"请求耗时: {duration:.2f} 秒")
        
        if response.status_code == 200:
            result = response.json()
            if result['success']:
                print("\n3. 异步获取成功:")
                for vm_name, status in result['results'].items():
                    print(f"   {vm_name}:")
                    print(f"     状态: {status['online_status']}")
                    print(f"     原因: {status['online_reason']}")
                    print(f"     IP: {status['ip']}")
                    print(f"     SSH互信: {'是' if status['ssh_trust'] else '否'}")
            else:
                print(f"\n3. 异步获取失败: {result['message']}")
        else:
            print(f"\n3. HTTP错误: {response.status_code}")
            print(f"响应内容: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("\n3. 连接错误: 无法连接到Flask服务")
        print("请确保Flask服务正在运行: python app.py")
    except requests.exceptions.Timeout:
        print("\n3. 请求超时: 异步获取耗时过长")
    except Exception as e:
        print(f"\n3. 请求异常: {str(e)}")
    
    print("\n测试完成!")

if __name__ == '__main__':
    test_async_online_status() 