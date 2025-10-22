#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接测试删除API端点的脚本
"""
import requests
import json
import time

# 获取数据库中的进程ID列表
def get_process_ids():
    try:
        # 首先运行check_db.py获取当前的进程ID列表
        import os
        import subprocess
        print("正在获取当前数据库中的进程记录...")
        result = subprocess.run(['python', 'check_db.py'], capture_output=True, text=True)
        print("check_db.py输出:")
        print(result.stdout)
        
        # 这里简单返回一个已知的进程ID作为示例
        # 实际使用时，用户应该从输出中选择一个有效的进程ID
        return "252c77c2-da01-4233-a2c5-cb45a6d1a91a"  # 假设这个ID存在
    except Exception as e:
        print(f"获取进程ID时出错: {e}")
        return None

# 测试删除API
def test_delete_api(process_id):
    if not process_id:
        print("错误: 没有有效的进程ID")
        return
    
    url = "http://localhost:5000/api/icloud/process/delete"
    headers = {"Content-Type": "application/json"}
    data = {"process_id": process_id}
    
    print(f"\n=== 开始测试删除API ===")
    print(f"目标URL: {url}")
    print(f"请求数据: {json.dumps(data)}")
    print(f"发送请求...")
    
    try:
        # 发送删除请求
        response = requests.post(url, headers=headers, json=data)
        
        print(f"\n=== API响应 ===")
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        # 尝试解析JSON响应
        try:
            json_response = response.json()
            print(f"响应体 (JSON):")
            print(json.dumps(json_response, indent=2, ensure_ascii=False))
        except ValueError:
            print(f"响应体 (原始):")
            print(response.text)
        
        print(f"\n=== 测试完成 ===")
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 请求异常: {e}")

if __name__ == "__main__":
    print("=====================================")
    print("       进程删除API测试脚本")
    print("=====================================")
    
    # 获取进程ID
    process_id = get_process_ids()
    
    # 让用户确认或输入进程ID
    user_input = input(f"\n请确认要删除的进程ID [{process_id}]: ")
    if user_input.strip():
        process_id = user_input.strip()
    
    # 执行删除测试
    test_delete_api(process_id)
    
    print("\n请检查后端日志以查看详细的删除操作记录。")