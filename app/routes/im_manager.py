import  threading
from flask import Blueprint, request, jsonify, render_template
from app.utils.common_utils import *
from app.utils.log_utils import logger
from app.utils.vm_utils import *

# 创建蓝图
im_manager_bp = Blueprint('im_manager', __name__)


# 批量IM状态
@im_manager_bp.route('/api/batch_im_status', methods=['POST'])
def batch_im_status():
    """批量IM状态查询API - 多线程异步版本"""
    try:
        data = request.get_json()
        vm_names = data.get('vm_names', [])
        session_id = data.get('session_id', str(uuid.uuid4()))

        if not vm_names:
            return jsonify({
                'success': False,
                'message': '请提供虚拟机名称列表'
            })

        # 启动异步处理
        thread = threading.Thread(target=process_batch_im_status_async, args=(vm_names, session_id))
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': '批量IM状态查询任务已启动，请通过WebSocket接收实时更新'
        })

    except Exception as e:
        logger.error(f"批量IM状态查询启动失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量IM状态查询启动失败: {str(e)}'
        })


# 批量IM注销
@im_manager_bp.route('/api/batch_im_logout', methods=['POST'])
def batch_im_logout():
    """批量IM注销API - 多线程异步版本"""
    try:
        data = request.get_json()
        vm_names = data.get('vm_names', [])
        session_id = data.get('session_id', str(uuid.uuid4()))

        if not vm_names:
            return jsonify({
                'success': False,
                'message': '请提供虚拟机名称列表'
            })

        # 启动异步处理
        thread = threading.Thread(target=process_batch_im_logout_async, args=(vm_names, session_id))
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': '批量IM注销任务已启动，请通过WebSocket接收实时更新'
        })

    except Exception as e:
        logger.error(f"批量IM注销启动失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量IM注销启动失败: {str(e)}'
        })

