import os
import json
import threading
import time
import sys
import base64
import subprocess
import uuid
from pathlib import Path
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, Response
from functools import wraps
from config import *
try:
    import paramiko
except ImportError:
    paramiko = None
try:
    import fcntl
except ImportError:
    fcntl = None
try:
    import msvcrt
except ImportError:
    msvcrt = None

# 尝试从ssh_utils导入setup_ssh_trust函数（本地函数中使用）
try:
    from app.utils.ssh_utils import *
    from app.utils.common_utils import logger
except ImportError:
    setup_ssh_trust = None



# 导入日志工具
from app.utils.log_utils import get_logger

# 创建虚拟机批量克隆蓝图
vm_clone_bp = Blueprint('vm_clone', __name__)

# 获取日志记录器
logger = get_logger(__name__)

# 定义日志目录
log_dir = logs_dir  # 从config.py导入的logs_dir

# 导入login_required装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 这里应该导入实际的login_required逻辑
        # 由于我们是从主应用移动过来，暂时保持简单
        return f(*args, **kwargs)
    return decorated_function


# 注意：clear_sessions_on_startup不应在此处调用，而应在应用主入口处调用一次
VM_DIRS = {
    '10_12': clone_dir,
    'chengpin': vm_chengpin_dir
}
clone_tasks = {}
tasks = {}
websockify_processes = {}  # 存储websockify进程信息



@vm_clone_bp.route('/api/clone_logs/<task_id>')
@login_required
def api_clone_logs(task_id):
    """获取克隆任务日志流"""

    def generate():
        try:
            if task_id not in clone_tasks:
                yield f"data: {json.dumps({'type': 'error', 'message': '任务不存在'})}\n\n"
                return

            task = clone_tasks[task_id]
            last_log_index = 0
            timeout_counter = 0
            max_timeout = 300  # 5分钟超时

            # 如果任务已完成，直接发送完成信号
            if task['status'] not in ['running']:
                try:
                    complete_data = {
                        'type': 'complete',
                        'success': task['status'] == 'completed',
                        'stats': task.get('stats', {})
                    }
                    yield f"data: {json.dumps(complete_data, ensure_ascii=False)}\n\n"
                except Exception as e:
                    logger.info(f"[DEBUG] 完成信号序列化失败: {str(e)}")
                    yield f"data: {json.dumps({'type': 'error', 'message': '完成信号序列化失败'})}\n\n"
                return

            while task['status'] in ['running'] and timeout_counter < max_timeout:
                # 发送新日志和进度数据
                has_new_data = False
                while last_log_index < len(task['logs']):
                    log_entry = task['logs'][last_log_index]
                    has_new_data = True

                    # 检查是否是进度数据或监控进度数据
                    if isinstance(log_entry, dict) and log_entry.get('type') in ['progress', 'monitoring_progress']:
                        # 发送进度数据
                        try:
                            yield f"data: {json.dumps(log_entry, ensure_ascii=False)}\n\n"
                        except Exception as e:
                            logger.info(f"[DEBUG] 进度数据序列化失败: {str(e)}")
                            yield f"data: {json.dumps({'type': 'error', 'message': '进度数据序列化失败'})}\n\n"
                    else:
                        # 发送普通日志
                        try:
                            # 确保消息是字符串类型
                            message = str(log_entry.get('message', ''))
                            log_data = {
                                'type': 'log',
                                'level': log_entry.get('level', 'info'),
                                'message': message
                            }
                            yield f"data: {json.dumps(log_data, ensure_ascii=False)}\n\n"
                        except Exception as e:
                            logger.info(f"[DEBUG] 日志数据序列化失败: {str(e)}")
                            yield f"data: {json.dumps({'type': 'error', 'message': '日志数据序列化失败'})}\n\n"

                    last_log_index += 1

                # 发送统计更新（只在有新数据时发送）
                if has_new_data:
                    try:
                        stats_data = {
                            'type': 'stats',
                            'stats': task['stats']
                        }
                        yield f"data: {json.dumps(stats_data, ensure_ascii=False)}\n\n"
                    except Exception as e:
                        logger.info(f"[DEBUG] 统计数据序列化失败: {str(e)}")
                        yield f"data: {json.dumps({'type': 'error', 'message': '统计数据序列化失败'})}\n\n"

                # 如果有新数据，减少等待时间以提高响应速度
                if has_new_data:
                    time.sleep(0.1)  # 有新数据时快速检查
                else:
                    time.sleep(0.5)  # 无新数据时稍微等待

                timeout_counter += 1

            # 发送完成信号
            try:
                complete_data = {
                    'type': 'complete',
                    'success': task['status'] == 'completed',
                    'stats': task['stats']
                }
                yield f"data: {json.dumps(complete_data, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.info(f"[DEBUG] 完成信号序列化失败: {str(e)}")
                yield f"data: {json.dumps({'type': 'error', 'message': '完成信号序列化失败'})}\n\n"

        except Exception as e:
            logger.info(f"[DEBUG] 日志流生成错误: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'日志流错误: {str(e)}'})}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@vm_clone_bp.route('/api/task_logs/<task_id>')
@login_required
def api_get_task_logs(task_id):
    """获取任务日志文件内容"""
    try:
        current_date = datetime.now().strftime('%Y-%m-%d')
        log_file_path = os.path.join(log_dir, f'task_{task_id}_{current_date}.log')
        if os.path.exists(log_file_path):
            with open(log_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({
                'status': 'success',
                'logs': content
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '日志文件不存在'
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'读取日志文件失败: {str(e)}'
        })



@vm_clone_bp.route('/api/vm_batch_clone', methods=['POST'])
@login_required
def api_vm_batch_clone():
    """虚拟机批量克隆接口"""
    logger.info("收到虚拟机批量克隆请求")
    try:
        data = request.get_json()
        
        # 验证请求参数
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据为空'
            })
        
        source_vm = data.get('source_vm')
        target_names = data.get('target_names', [])
        
        if not source_vm:
            return jsonify({
                'success': False,
                'message': '源虚拟机未指定'
            })
        
        if not target_names:
            return jsonify({
                'success': False,
                'message': '目标虚拟机名称列表为空'
            })
        
        logger.info(f"源虚拟机: {source_vm}, 目标虚拟机数量: {len(target_names)}")
        
        # TODO: 实现实际的批量克隆逻辑
        # 这里应该添加实际的虚拟机克隆代码
        # 可能需要调用vmrun或其他虚拟机管理工具
        
        # 返回模拟的成功响应
        return jsonify({
            'success': True,
            'message': f'已开始批量克隆任务，将创建 {len(target_names)} 个虚拟机',
            'data': {
                'source_vm': source_vm,
                'target_count': len(target_names),
                'task_id': f"clone_task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            }
        })
        
    except Exception as e:
        logger.error(f"虚拟机批量克隆失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'虚拟机批量克隆失败: {str(e)}'
        })

@vm_clone_bp.route('/api/clone_task_status/<task_id>')
@login_required
def api_clone_task_status(task_id):
    """获取克隆任务状态"""
    logger.info(f"查询克隆任务状态: {task_id}")
    try:
        # TODO: 实现实际的任务状态查询逻辑
        # 这里应该从任务存储中获取实际的任务状态
        
        # 返回模拟的任务状态
        return jsonify({
            'success': True,
            'data': {
                'task_id': task_id,
                'status': 'running',  # pending, running, completed, failed
                'progress': 50,
                'completed_count': 5,
                'total_count': 10,
                'message': '克隆任务进行中'
            }
        })
    except Exception as e:
        logger.error(f"获取克隆任务状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取克隆任务状态失败: {str(e)}'
        })


@vm_clone_bp.route('/api/clone_vm', methods=['POST'])
@login_required
def api_clone_vm():
    """启动克隆虚拟机任务"""
    logger.info("收到克隆虚拟机API请求")
    try:
        data = request.get_json()
        logger.debug(f"API收到克隆请求参数: {data}")

        # 验证必要参数
        required_fields = ['templateVM', 'cloneCount', 'targetDir', 'namingPattern', 'configPlist']
        for field in required_fields:
            if not data.get(field):
                logger.warning(f"缺少必要参数: {field}")
                return jsonify({'success': False, 'message': f'缺少必要参数: {field}'})

        # 验证可用五码数量
        config_file = data.get('configPlist')
        clone_count = int(data.get('cloneCount'))

        logger.debug(f"配置文件: {config_file}")
        logger.debug(f"克隆数量: {clone_count}")
        logger.debug(f"配置文件是否存在: {os.path.exists(config_file)}")

        if os.path.exists(config_file):
            # 计算可用五码数量
            available_wuma_count = count_available_wuma(config_file)

            logger.debug(f"可用五码数量: {available_wuma_count}")

            if available_wuma_count < clone_count:
                logger.warning(f"可用五码不足: 需要{clone_count}个，只有{available_wuma_count}个")
                return jsonify({
                    'success': False,
                    'message': f'可用五码不足：配置文件中有 {available_wuma_count} 个可用五码，但需要克隆 {clone_count} 个虚拟机。请增加五码配置或减少克隆数量。'
                })
        else:
            logger.error(f"配置文件不存在: {config_file}")
            return jsonify({'success': False, 'message': f'配置文件不存在: {config_file}'})

        # 生成任务ID
        task_id = str(uuid.uuid4())
        logger.info(f"生成克隆任务ID: {task_id}")

        # 创建任务对象
        task = {
            'id': task_id,
            'status': 'running',
            'params': data,
            'logs': [],
            'stats': {'success': 0, 'running': 0, 'error': 0, 'total': int(data['cloneCount'])},
            'start_time': datetime.now(),
            'progress': {'current': 0, 'total': int(data['cloneCount'])}
        }

        clone_tasks[task_id] = task
        logger.debug(f"克隆任务已创建并存储")

        # 启动克隆线程
        thread = threading.Thread(target=clone_vm_worker, args=(task_id,))
        thread.daemon = True
        thread.start()
        logger.info(f"克隆线程已启动，任务ID: {task_id}")

        return jsonify({'success': True, 'task_id': task_id})

    except Exception as e:
        logger.error(f"克隆虚拟机API异常: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})


