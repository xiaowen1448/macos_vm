#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试VNC连接清理功能
"""

import requests
import json
import time

def test_cleanup_all_vnc():
    """测试清理所有VNC连接的API"""
    
    session = requests.Session()
    
    # 先访问登录页面获取session
    print("1. 访问登录页面...")
    login_page_response = session.get('http://127.0.0.1:5000/login')
    if login_page_response.status_code != 200:
        print(f"✗ 访问登录页面失败: {login_page_response.status_code}")
        return False
    
    # 登录获取session
    login_url = 'http://127.0.0.1:5000/login'
    login_data = {
        'username': 'admin',
        'password': '123456'
    }
    
    print("2. 登录系统...")
    response = session.post(login_url, data=login_data, allow_redirects=True)
    
    # 检查登录是否成功
    if response.status_code == 200:
        # 检查是否包含登录成功的标识（比如不再是登录页面）
        if 'login' not in response.url and ('dashboard' in response.text or 'logout' in response.text or '退出' in response.text):
            print("✓ 登录成功")
        else:
            print("✗ 登录失败: 可能用户名或密码错误")
            return False
    else:
        print(f"✗ 登录失败: {response.status_code}")
        print(f"响应内容: {response.text[:500]}...")
        return False
    
    # 测试清理所有VNC连接API
    cleanup_url = 'http://127.0.0.1:5000/api/vnc/cleanup_all'
    
    print("\n3. 调用清理所有VNC连接API...")
    try:
        # 添加必要的请求头
        headers = {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'  # 标识为AJAX请求
        }
        
        response = session.post(cleanup_url, headers=headers, json={})
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
            
            if data.get('success'):
                print("✓ VNC连接清理成功")
                print(f"消息: {data.get('message')}")
                return True
            else:
                print(f"✗ VNC连接清理失败: {data.get('message')}")
                return False
        else:
            print(f"✗ API调用失败: {response.status_code}")
            try:
                error_data = response.json()
                print(f"错误信息: {json.dumps(error_data, ensure_ascii=False, indent=2)}")
            except:
                print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ 请求异常: {str(e)}")
        return False

def check_websockify_processes():
    """检查websockify进程状态"""
    import subprocess
    
    print("\n3. 检查websockify进程状态...")
    try:
        # 检查websockify进程
        result = subprocess.run(['tasklist'], capture_output=True, text=True, shell=True)
        output = result.stdout
        
        websockify_processes = []
        for line in output.split('\n'):
            if 'python' in line.lower() and any(keyword in line for keyword in ['websockify', 'python']):
                websockify_processes.append(line.strip())
        
        if websockify_processes:
            print(f"发现 {len(websockify_processes)} 个Python进程:")
            for proc in websockify_processes:
                print(f"  {proc}")
        else:
            print("✓ 未发现websockify相关进程")
            
        # 检查6080端口占用
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, shell=True)
        output = result.stdout
        
        port_6080_processes = []
        for line in output.split('\n'):
            if ':6080' in line and 'LISTENING' in line:
                port_6080_processes.append(line.strip())
        
        if port_6080_processes:
            print(f"\n发现 {len(port_6080_processes)} 个进程占用6080端口:")
            for proc in port_6080_processes:
                print(f"  {proc}")
        else:
            print("\n✓ 6080端口未被占用")
            
    except Exception as e:
        print(f"✗ 检查进程状态失败: {str(e)}")

def main():
    """主函数"""
    print("=== VNC连接清理功能测试 ===")
    
    # 先检查当前进程状态
    print("\n--- 清理前状态检查 ---")
    check_websockify_processes()
    
    # 测试清理API
    print("\n--- 执行清理操作 ---")
    success = test_cleanup_all_vnc()
    
    # 等待一段时间让清理操作完成
    if success:
        print("\n等待3秒让清理操作完成...")
        time.sleep(3)
        
        # 再次检查进程状态
        print("\n--- 清理后状态检查 ---")
        check_websockify_processes()
    
    print("\n=== 测试完成 ===")

if __name__ == '__main__':
    main()