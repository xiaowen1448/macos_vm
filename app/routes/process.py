from flask import Blueprint, jsonify, request
from datetime import datetime

# 创建蓝图
process_bp = Blueprint('process', __name__)

# 进程列表数据存储（示例数据）
processes = [
    {
        "id": "1",
        "name": "iMessage登录进程",
        "script": "login_imessage.scpt",
        "client": "VM_20250913",
        "apple_id": "test@icloud.com",
        "status": "已停止",
        "create_time": "2025-10-22 10:00:00"
    }
]

# 进程管理路由
@process_bp.route('/api/process/list')
def get_process_list():
    return jsonify({
        "success": True,
        "data": processes
    })

@process_bp.route('/api/process/add', methods=['POST'])
def add_process():
    data = request.json
    new_process = {
        "id": str(len(processes) + 1),
        "name": data.get('process_name'),
        "script": data.get('process_script'),
        "client": data.get('process_client'),
        "apple_id": data.get('apple_id'),
        "status": "已停止",
        "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    processes.append(new_process)
    return jsonify({
        "success": True,
        "message": "进程添加成功",
        "data": new_process
    })

@process_bp.route('/api/process/start', methods=['POST'])
def start_process():
    process_id = request.json.get('process_id')
    for process in processes:
        if process['id'] == process_id:
            process['status'] = '执行中'
            return jsonify({
                "success": True,
                "message": "进程已启动"
            })
    return jsonify({
        "success": False,
        "message": "找不到指定进程"
    })

@process_bp.route('/api/process/stop', methods=['POST'])
def stop_process():
    process_id = request.json.get('process_id')
    for process in processes:
        if process['id'] == process_id:
            process['status'] = '已停止'
            return jsonify({
                "success": True,
                "message": "进程已停止"
            })
    return jsonify({
        "success": False,
        "message": "找不到指定进程"
    })

@process_bp.route('/api/process/delete', methods=['POST'])
def delete_process():
    process_id = request.json.get('process_id')
    global processes
    processes = [p for p in processes if p['id'] != process_id]
    return jsonify({
        "success": True,
        "message": "进程已删除"
    })

@process_bp.route('/api/process/detail/<process_id>')
def get_process_detail(process_id):
    for process in processes:
        if process['id'] == process_id:
            return jsonify({
                "success": True,
                "data": process
            })
    return jsonify({
        "success": False,
        "message": "找不到指定进程"
    })