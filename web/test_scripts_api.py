#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(__file__))

from app import api_scripts
from flask import Flask
import json

def test_scripts_api():
    """测试脚本API功能"""
    print("测试脚本API功能...")
    
    # 创建测试Flask应用
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    with app.test_request_context('/api/scripts'):
        try:
            # 模拟登录状态
            from flask import session
            session['logged_in'] = True
            
            # 调用API
            response = api_scripts()
            data = json.loads(response.get_data(as_text=True))
            
            print(f"API响应: {data}")
            
            if data['success']:
                print(f"\n✅ API调用成功")
                print(f"找到 {len(data['scripts'])} 个脚本文件:")
                
                for script in data['scripts']:
                    print(f"  - {script['name']} ({script['size']}) - {script['modified_time']}")
            else:
                print(f"\n❌ API调用失败: {data['message']}")
                
        except Exception as e:
            print(f"\n❌ 测试失败: {str(e)}")
    
    print("\n测试完成!")

if __name__ == '__main__':
    test_scripts_api() 