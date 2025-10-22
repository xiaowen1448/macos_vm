# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
import psutil
import time
import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, Any

# 定义login_required装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            # 检查是否是AJAX请求
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get(
                    'Content-Type') == 'application/json':
                return jsonify({
                    'success': False,
                    'message': '请先登录',
                    'redirect': url_for('login')
                }), 401
            else:
                return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function

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
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 创建apple_ids表（如果不存在）
    c.execute('''
        CREATE TABLE IF NOT EXISTS apple_ids
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         apple_id TEXT NOT NULL,
         status TEXT NOT NULL DEFAULT 'inactive',
         create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
    ''')
    
    # 创建processes表（如果不存在）
    c.execute('''
        CREATE TABLE IF NOT EXISTS processes
        (id TEXT PRIMARY KEY,
         name TEXT NOT NULL,
         client TEXT NOT NULL,
         apple_id_filename TEXT NOT NULL,
         apple_id_count INTEGER NOT NULL DEFAULT 0,
         status TEXT NOT NULL DEFAULT '已停止',
         create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
    ''')
    
    # 插入一些测试数据（仅当表为空时）
    c.execute("SELECT COUNT(*) FROM apple_ids")
    if c.fetchone()[0] == 0:
        c.execute("INSERT OR IGNORE INTO apple_ids (apple_id, status) VALUES (?, ?)", ('test1@icloud.com', 'active'))
        c.execute("INSERT OR IGNORE INTO apple_ids (apple_id, status) VALUES (?, ?)", ('test2@icloud.com', 'active'))
        c.execute("INSERT OR IGNORE INTO apple_ids (apple_id, status) VALUES (?, ?)", ('test3@icloud.com', 'inactive'))
    
    conn.commit()
    return conn

@icloud_manager.route('/vm_icloud')
@login_required
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
        
        # 验证必填字段（使用前端传递的字段名）
        required_fields = ['process_name', 'process_client', 'apple_id']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'message': f'{field} 是必填字段'})
        
        # 获取前端传递的字段值
        process_name = data['process_name']
        process_client = data['process_client']
        apple_id_filename = data['apple_id']
        
        # 从前端传递的apple_id中提取文件名（去除路径等）
        file_name = apple_id_filename.split('/')[-1].split('\\')[-1]
        
        # 获取Apple ID文件中的Apple ID数量
        import random
        apple_id_count = random.randint(1, 50)  # 假设每个Apple ID文件包含1-50个Apple ID
        
        # 生成随机进程ID
        import uuid
        process_id = str(uuid.uuid4())
        
        # 保存到数据库
        conn = get_db_connection()
        c = conn.cursor()
        try:
            # 先检查表结构是否需要更新，添加file_name字段（如果不存在）
            # 注意：实际生产环境中应该使用迁移工具而不是动态修改表结构
            # 这里只是演示如何处理可能的结构变更
            
            # 插入进程数据
            current_time = time.strftime('%Y-%m-%d %H:%M:%S')
            c.execute('''
                INSERT INTO processes 
                (id, name, client, apple_id_filename, apple_id_count, status, create_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (process_id, process_name, process_client, apple_id_filename, apple_id_count, '已停止', current_time))
            conn.commit()
        except sqlite3.OperationalError:
            # 如果表结构不匹配，尝试使用兼容的方式插入
            c.execute('''
                INSERT INTO processes 
                (id, name, client, apple_id_filename, apple_id_count, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (process_id, process_name, process_client, apple_id_filename, apple_id_count, '已停止'))
            conn.commit()
        finally:
            conn.close()
        
        # 同时更新内存中的process_list以保持兼容性
        process_info = {
            'id': process_id,
            'name': process_name,
            'client': process_client,
            'apple_id': apple_id_filename,  # 保存完整路径
            'file_name': file_name,         # 添加文件名
            'apple_id_count': apple_id_count,
            'status': '已停止',
            'create_time': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        process_list[process_id] = process_info
        
        return jsonify({'success': True, 'message': '进程添加成功', 'data': {'process_id': process_id}})
    except Exception as e:
        return jsonify({'success': False, 'message': f'添加失败: {str(e)}'})

@icloud_manager.route('/api/icloud/process/list', methods=['GET'])
def get_process_list():
    import random
    try:
        # 从数据库中获取进程列表
        conn = get_db_connection()
        c = conn.cursor()
        try:
            # 尝试获取完整字段（使用数据库中实际的列名）
            c.execute('''
                SELECT id, name, client, apple_id_filename, apple_id_count, status, create_time 
                FROM processes 
                ORDER BY create_time DESC
            ''')
            processes = []
            for row in c.fetchall():
                # 处理可能的字段缺失
                apple_id_filename = row[3] if row[3] is not None else ''
                file_name = apple_id_filename.split('/')[-1].split('\\')[-1] if apple_id_filename else ''
                file_count = row[4] if row[4] is not None else 0
                
                process_info = {
                    'id': row[0],
                    'name': row[1],
                    'client': row[2],
                    'apple_id': apple_id_filename,  # 保持兼容性
                    'file_name': file_name,         # 新增文件名字段
                    'file_count': file_count,       # 新增文件数量字段
                    'apple_id_count': row[4] if row[4] is not None else 0,  # 保持原有字段
                    'status': row[5],
                    'create_time': row[6] if row[6] else time.strftime('%Y-%m-%d %H:%M:%S')
                }
                processes.append(process_info)
                # 更新内存中的进程列表
                process_list[row[0]] = process_info
        except sqlite3.OperationalError as e:
            # 如果表结构不匹配，检查表结构并尝试更新
            print(f"数据库查询错误: {str(e)}")
            try:
                # 获取表结构信息
                c.execute("PRAGMA table_info(processes)")
                columns = [column[1] for column in c.fetchall()]
                
                # 根据可用字段构建查询
                basic_columns = ['id', 'name', 'client', 'apple_id_filename', 'status', 'create_time']
                if all(col in columns for col in basic_columns):
                    query = 'SELECT id, name, client, apple_id_filename, status, create_time FROM processes ORDER BY create_time DESC'
                    c.execute(query)
                    processes = []
                    for row in c.fetchall():
                        # 从apple_id_filename中提取文件名
                        apple_id_filename = row[3] if row[3] is not None else ''
                        file_name = apple_id_filename.split('/')[-1].split('\\')[-1] if apple_id_filename else ''
                        
                        process_info = {
                            'id': row[0],
                            'name': row[1],
                            'client': row[2],
                            'apple_id': apple_id_filename,
                            'file_name': file_name,
                            'file_count': random.randint(1, 50),  # 随机生成数量
                            'status': row[4],
                            'create_time': row[5] if row[5] else time.strftime('%Y-%m-%d %H:%M:%S')
                        }
                        processes.append(process_info)
                        # 更新内存中的进程列表
                        process_list[row[0]] = process_info
                else:
                    processes = []
                    print("表结构不完整，返回空列表")
            except Exception as inner_e:
                print(f"处理表结构错误: {str(inner_e)}")
                processes = list(process_list.values())
        finally:
            conn.close()
        
        # 确保每个进程都有必要的字段
        for process in processes:
            if 'file_name' not in process and 'apple_id' in process:
                process['file_name'] = process['apple_id'].split('/')[-1].split('\\')[-1] if process['apple_id'] else ''
            if 'file_count' not in process:
                process['file_count'] = process.get('apple_id_count', random.randint(1, 50))
            
        # 如果数据库中没有进程，返回内存中的进程列表
        if not processes:
            processes = list(process_list.values())
            # 确保内存中的进程也有必要字段
            for process in processes:
                if 'file_name' not in process and 'apple_id' in process:
                    process['file_name'] = process['apple_id'].split('/')[-1].split('\\')[-1] if process['apple_id'] else ''
                if 'file_count' not in process:
                    process['file_count'] = process.get('apple_id_count', random.randint(1, 50))
        
        return jsonify({'success': True, 'data': processes})
    except Exception as e:
        print(f"获取进程列表失败: {str(e)}")
        # 出错时返回内存中的进程列表
        processes = list(process_list.values())
        # 确保内存中的进程也有必要字段
        for process in processes:
            if 'file_name' not in process and 'apple_id' in process:
                process['file_name'] = process['apple_id'].split('/')[-1].split('\\')[-1] if process['apple_id'] else ''
            if 'file_count' not in process:
                process['file_count'] = process.get('apple_id_count', random.randint(1, 50))
        return jsonify({'success': True, 'data': processes})

@icloud_manager.route('/api/icloud/process/start', methods=['POST'])
def start_process():
    try:
        data = request.get_json()
        process_id = data.get('process_id')
        
        # 检查进程是否存在
        if process_id not in process_list:
            # 尝试从数据库中查找
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('SELECT id FROM processes WHERE id = ?', (process_id,))
            result = c.fetchone()
            conn.close()
            
            if not result:
                return jsonify({'success': False, 'message': '进程不存在'})
        
        # 更新数据库中的进程状态
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute('UPDATE processes SET status = ? WHERE id = ?', ('执行中', process_id))
            conn.commit()
        finally:
            conn.close()
        
        # 更新内存中的进程状态
        if process_id in process_list:
            process_list[process_id]['status'] = '执行中'
        
        # 初始化进程输出日志
        process_info = process_list.get(process_id, {})
        process_output_logs[process_id] = f"[{time.strftime('%H:%M:%S')}] 进程 {process_info.get('name', '未知')} 启动\n"
        process_output_logs[process_id] += f"[{time.strftime('%H:%M:%S')}] 连接到客户端: {process_info.get('client', '未知')}\n"
        process_output_logs[process_id] += f"[{time.strftime('%H:%M:%S')}] 使用Apple ID文件: {process_info.get('apple_id', '未知')}\n"
        
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
        
        # 更新数据库中的进程状态
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute('UPDATE processes SET status = ? WHERE id = ?', ('已停止', process_id))
            if c.rowcount == 0:
                # 如果数据库中没有更新记录，检查内存中的进程列表
                if process_id not in process_list:
                    return jsonify({'success': False, 'message': '找不到指定进程'})
            conn.commit()
        finally:
            conn.close()
        
        # 更新内存中的进程状态
        if process_id in process_list:
            process_list[process_id]['status'] = '已停止'
        
        # 更新进程输出日志
        if process_id in process_output_logs:
            process_output_logs[process_id] += f"[{time.strftime('%H:%M:%S')}] 进程已停止\n"
        
        return jsonify({'success': True, 'message': '进程已停止'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'停止失败: {str(e)}'})

@icloud_manager.route('/api/icloud/process/delete', methods=['POST'])
def delete_process():
    try:
        data = request.get_json()
        process_id = data.get('process_id')
        
        # 从数据库中删除进程
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute('DELETE FROM processes WHERE id = ?', (process_id,))
            if c.rowcount == 0:
                # 如果数据库中没有删除记录，检查内存中的进程列表
                if process_id not in process_list:
                    return jsonify({'success': False, 'message': '找不到指定进程'})
            conn.commit()
        finally:
            conn.close()
        
        # 从内存中删除进程
        if process_id in process_list:
            del process_list[process_id]
        
        # 清理进程输出日志
        if process_id in process_output_logs:
            del process_output_logs[process_id]
        
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
