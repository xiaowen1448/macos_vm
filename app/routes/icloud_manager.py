# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, jsonify
import psutil
import time
import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, Any

icloud_manager = Blueprint('icloud_manager', __name__)

# 存储进程信息的字典，预设一些测试数据
process_list = {
    '1698000001': {
        'id': '1698000001',
        'name': '自动登录进程1',
        'script': 'login_imessage.scpt',
        'client': 'VM_001',
        'apple_id': 'test1@icloud.com',
        'status': '执行中',
        'create_time': '2025-10-22 10:00:00'
    },
    '1698000002': {
        'id': '1698000002',
        'name': '消息发送进程2',
        'script': 'send_imessage.scpt',
        'client': 'VM_002',
        'apple_id': 'test2@icloud.com',
        'status': '已停止',
        'create_time': '2025-10-22 11:00:00'
    },
    '1698000003': {
        'id': '1698000003',
        'name': '账号注销进程3',
        'script': 'logout_imessage.scpt',
        'client': 'VM_003',
        'apple_id': 'test3@icloud.com',
        'status': '错误',
        'create_time': '2025-10-22 12:00:00'
    },
    '1698000004': {
        'id': '1698000004',
        'name': '批量登录进程4',
        'script': 'batch_login.scpt',
        'client': 'VM_004',
        'apple_id': 'test4@icloud.com',
        'status': '执行完成',
        'create_time': '2025-10-22 13:00:00'
    }
}
def get_db_connection():
    """获取数据库连接"""
    # 使用绝对路径确保数据库文件正确创建
    db_dir = Path(__file__).parent.parent.parent / 'db'
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / 'apple_ids.db'
    
    if not db_path.exists():
        # 创建数据库文件和表
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS apple_ids
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             apple_id TEXT NOT NULL,
             status TEXT NOT NULL DEFAULT 'inactive',
             create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        ''')
        # 插入一些测试数据
        c.execute("INSERT OR IGNORE INTO apple_ids (apple_id, status) VALUES (?, ?)", ('test1@icloud.com', 'active'))
        c.execute("INSERT OR IGNORE INTO apple_ids (apple_id, status) VALUES (?, ?)", ('test2@icloud.com', 'active'))
        c.execute("INSERT OR IGNORE INTO apple_ids (apple_id, status) VALUES (?, ?)", ('test3@icloud.com', 'inactive'))
        conn.commit()
        conn.close()
    return sqlite3.connect(db_path)

@icloud_manager.route('/vm_icloud')
def vm_icloud():
    return render_template('vm_icloud.html')

@icloud_manager.route('/api/id/list', methods=['GET'])
def get_apple_id_list():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT id, apple_id, status FROM apple_ids')
        apple_ids = [{'id': row[0], 'apple_id': row[1], 'status': row[2]} for row in c.fetchall()]
        conn.close()
        return jsonify({'success': True, 'data': apple_ids})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取Apple ID列表失败: {str(e)}'})

# 存储进程输出日志的字典
process_output_logs = {}

@icloud_manager.route('/api/icloud/process/add', methods=['POST'])
def add_process():
    try:
        data = request.get_json()
        process_name = data.get('process_name')
        process_client = data.get('process_client')
        apple_id = data.get('apple_id')
        
        # 检查Apple ID是否存在
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT apple_id FROM apple_ids WHERE id = ?', (apple_id,))
        result = c.fetchone()
        conn.close()
        
        if not result:
            return jsonify({'success': False, 'message': 'Apple ID不存在'})
        
        # 生成唯一进程ID
        process_id = str(int(time.time()))
        
        process_info = {
            'id': process_id,
            'name': process_name,
            'script': '',  # 不再需要脚本
            'client': process_client,
            'apple_id': result[0],  # 使用实际的Apple ID而不是ID号
            'status': '已停止',  # 初始状态
            'create_time': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        process_list[process_id] = process_info
        return jsonify({'success': True, 'message': '进程添加成功', 'process_id': process_id})
    except Exception as e:
        return jsonify({'success': False, 'message': f'添加失败: {str(e)}'})

@icloud_manager.route('/api/icloud/process/list', methods=['GET'])
def get_process_list():
    return jsonify({'success': True, 'data': list(process_list.values())})

@icloud_manager.route('/api/icloud/process/start', methods=['POST'])
def start_process():
    try:
        data = request.get_json()
        process_id = data.get('process_id')
        
        if process_id not in process_list:
            return jsonify({'success': False, 'message': '进程不存在'})
        
        # 初始化进程输出日志
        process_info = process_list[process_id]
        process_output_logs[process_id] = f"[{time.strftime('%H:%M:%S')}] 进程 {process_info['name']} 启动\n"
        process_output_logs[process_id] += f"[{time.strftime('%H:%M:%S')}] 连接到客户端: {process_info['client']}\n"
        process_output_logs[process_id] += f"[{time.strftime('%H:%M:%S')}] 使用Apple ID: {process_info['apple_id']}\n"
        
        # 更新进程状态
        process_list[process_id]['status'] = '执行中'
        return jsonify({'success': True, 'message': '进程已启动'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'启动失败: {str(e)}'})

@icloud_manager.route('/api/icloud/process/stop', methods=['POST'])
def stop_process():
    try:
        data = request.get_json()
        process_id = data.get('process_id')
        
        if process_id not in process_list:
            return jsonify({'success': False, 'message': '进程不存在'})
        
        # 这里添加实际停止进程的逻辑
        process_list[process_id]['status'] = '已停止'
        return jsonify({'success': True, 'message': '进程已停止'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'停止失败: {str(e)}'})

@icloud_manager.route('/api/icloud/process/delete', methods=['POST'])
def delete_process():
    try:
        data = request.get_json()
        process_id = data.get('process_id')
        
        if process_id not in process_list:
            return jsonify({'success': False, 'message': '进程不存在'})
        
        # 如果进程正在运行，先停止它
        if process_list[process_id]['status'] == '执行中':
            # 添加停止进程的逻辑
            pass
        
        del process_list[process_id]
        return jsonify({'success': True, 'message': '进程已删除'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})

@icloud_manager.route('/api/icloud/process/detail/<process_id>')
def get_process_detail(process_id):
    if process_id not in process_list:
        return jsonify({'success': False, 'message': '进程不存在'})
    return jsonify({'success': True, 'data': process_list[process_id]})



@icloud_manager.route('/api/icloud/process/output/<process_id>')
def get_process_output(process_id):
    try:
        if process_id not in process_list:
            return jsonify({'success': False, 'message': '进程不存在'})
        
        # 获取进程输出，如果不存在则返回模拟输出
        if process_id not in process_output_logs:
            # 为旧进程生成模拟输出
            process_info = process_list[process_id]
            output = f"[{time.strftime('%H:%M:%S')}] 进程 {process_info['name']} 输出日志\n"
            output += f"[{time.strftime('%H:%M:%S')}] 客户端: {process_info['client']}\n"
            output += f"[{time.strftime('%H:%M:%S')}] Apple ID: {process_info['apple_id']}\n"
            output += f"[{time.strftime('%H:%M:%S')}] 状态: {process_info['status']}\n"
            
            if process_info['status'] == '执行中':
                output += f"[{time.strftime('%H:%M:%S')}] 正在执行操作...\n"
                output += f"[{time.strftime('%H:%M:%S')}] 处理进度: 50%\n"
            elif process_info['status'] == '已停止':
                output += f"[{time.strftime('%H:%M:%S')}] 进程已停止\n"
            elif process_info['status'] == '执行完成':
                output += f"[{time.strftime('%H:%M:%S')}] 进程执行完成\n"
                output += f"[{time.strftime('%H:%M:%S')}] 结果: 成功\n"
            elif process_info['status'] == '错误':
                output += f"[{time.strftime('%H:%M:%S')}] 执行过程中出现错误\n"
                output += f"[{time.strftime('%H:%M:%S')}] 错误信息: 连接超时\n"
            
            return jsonify({'success': True, 'output': output})
        
        # 如果进程正在运行，添加一些动态输出
        if process_list[process_id]['status'] == '执行中':
            # 添加一些模拟的进度更新
            import random
            progress = random.randint(0, 100)
            actions = ['正在连接客户端...', '正在验证账号...', '正在执行操作...', '正在同步数据...', '处理中...']
            random_action = random.choice(actions)
            process_output_logs[process_id] += f"[{time.strftime('%H:%M:%S')}] {random_action} - 进度: {progress}%\n"
        
        return jsonify({'success': True, 'output': process_output_logs[process_id]})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取进程输出失败: {str(e)}', 'output': f'错误: {str(e)}'})
