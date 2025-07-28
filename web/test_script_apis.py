#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(__file__))

from app import api_scripts, api_get_script_content, api_edit_script, api_send_script
from flask import Flask
import json

def test_script_apis():
    """测试脚本相关API功能"""
    print("测试脚本相关API功能...")
    
    # 创建测试Flask应用
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    with app.test_request_context('/api/scripts'):
        try:
            # 模拟登录状态
            from flask import session
            session['logged_in'] = True
            
            print("\n1. 测试获取脚本列表API")
            response = api_scripts()
            data = json.loads(response.get_data(as_text=True))
            
            if data['success']:
                print(f"✅ 获取脚本列表成功，找到 {len(data['scripts'])} 个脚本")
                for script in data['scripts']:
                    print(f"  - {script['name']} ({script['size']}) - 备注: {script.get('note', '无')}")
            else:
                print(f"❌ 获取脚本列表失败: {data['message']}")
                return
            
            if not data['scripts']:
                print("⚠️  没有找到脚本文件，跳过后续测试")
                return
            
            # 测试获取脚本内容
            test_script = data['scripts'][0]['name']
            print(f"\n2. 测试获取脚本内容API: {test_script}")
            
            with app.test_request_context(f'/api/script/content/{test_script}'):
                session['logged_in'] = True
                response = api_get_script_content(test_script)
                content_data = json.loads(response.get_data(as_text=True))
                
                if content_data['success']:
                    print(f"✅ 获取脚本内容成功")
                    print(f"  内容长度: {len(content_data['content'])} 字符")
                    print(f"  备注: {content_data.get('note', '无')}")
                else:
                    print(f"❌ 获取脚本内容失败: {content_data['message']}")
            
            # 测试编辑脚本
            print(f"\n3. 测试编辑脚本API: {test_script}")
            
            with app.test_request_context('/api/script/edit', method='POST', json={
                'script_name': test_script,
                'content': '#!/bin/bash\necho "测试脚本内容"\n',
                'note': '这是一个测试备注'
            }):
                session['logged_in'] = True
                response = api_edit_script()
                edit_data = json.loads(response.get_data(as_text=True))
                
                if edit_data['success']:
                    print(f"✅ 编辑脚本成功")
                else:
                    print(f"❌ 编辑脚本失败: {edit_data['message']}")
            
            # 测试发送脚本
            print(f"\n4. 测试发送脚本API: {test_script}")
            
            with app.test_request_context('/api/script/send', method='POST', json={
                'script_name': test_script,
                'vm_names': ['test_vm']
            }):
                session['logged_in'] = True
                response = api_send_script()
                send_data = json.loads(response.get_data(as_text=True))
                
                if send_data['success']:
                    print(f"✅ 发送脚本API调用成功")
                    print(f"  发送结果: {len(send_data['results'])} 个虚拟机")
                    for result in send_data['results']:
                        print(f"    {result['vm_name']}: {result['status']} - {result['message']}")
                else:
                    print(f"❌ 发送脚本失败: {send_data['message']}")
            
        except Exception as e:
            print(f"\n❌ 测试失败: {str(e)}")
    
    print("\n测试完成!")

if __name__ == '__main__':
    test_script_apis() 