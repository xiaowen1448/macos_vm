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
    # 重定向到icloud_process.py中的完整实现
    from flask import redirect, url_for
    return redirect(url_for('icloud_process.get_process_list'))

@process_bp.route('/api/process/add', methods=['POST'])
def add_process():
    # 重定向到icloud_process.py中的完整实现
    from flask import redirect, url_for
    return redirect(url_for('icloud_process.add_process'), code=307)  # 307保持原始方法

@process_bp.route('/api/process/start', methods=['POST'])
def start_process():
    # 重定向到icloud_process.py中的完整实现
    from flask import redirect, url_for
    return redirect(url_for('icloud_process.start_process'), code=307)  # 307保持原始方法

@process_bp.route('/api/process/stop', methods=['POST'])
def stop_process():
    # 重定向到icloud_process.py中的完整实现
    from flask import redirect, url_for
    return redirect(url_for('icloud_process.stop_process'), code=307)  # 307保持原始方法

@process_bp.route('/api/process/delete', methods=['POST'])
def delete_process():
    # 重定向到icloud_process.py中的完整实现
    from flask import redirect, url_for
    return redirect(url_for('icloud_process.delete_process'), code=307)  # 307保持原始方法

@process_bp.route('/api/process/detail/<process_id>')
def get_process_detail(process_id):
    # 重定向到icloud_process.py中的完整实现
    from flask import redirect, url_for
    return redirect(url_for('icloud_process.get_process_detail', process_id=process_id))

# Session检查路由，用于前端检测session是否过期
@process_bp.route('/api/check_session')
def check_session():
    from flask import session, jsonify
    # 检查session中是否有用户信息（具体的键名可能需要根据实际情况调整）
    # 这里假设session中存储了'user_id'或'logged_in'标志
    if 'user_id' in session or 'logged_in' in session:
        return jsonify({'session_expired': False})
    else:
        return jsonify({'session_expired': True})