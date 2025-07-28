#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

def test_api():
    """直接测试API"""
    base_url = "http://localhost:5000"
    
    # 测试分页大小5
    print("=== 测试分页大小5 ===")
    response = requests.get(f"{base_url}/api/scripts?page=1&page_size=5")
    if response.status_code == 200:
        data = response.json()
        print(f"脚本数量: {len(data['scripts'])}")
        print(f"脚本列表: {[script['name'] for script in data['scripts']]}")
        print(f"分页信息: {data['pagination']}")
    else:
        print(f"请求失败: {response.status_code}")
    
    print("\n=== 测试分页大小10 ===")
    response = requests.get(f"{base_url}/api/scripts?page=1&page_size=10")
    if response.status_code == 200:
        data = response.json()
        print(f"脚本数量: {len(data['scripts'])}")
        print(f"脚本列表: {[script['name'] for script in data['scripts']]}")
        print(f"分页信息: {data['pagination']}")
    else:
        print(f"请求失败: {response.status_code}")

if __name__ == "__main__":
    test_api() 