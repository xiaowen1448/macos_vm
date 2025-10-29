import os 
from datetime import datetime
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from flask_socketio import SocketIO, emit
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from app.utils import ssh_utils
from config import *
from app.utils.ssh_utils import SSHClient
from app.utils.vm_utils import *
from app.utils.common_utils import clear_sessions_on_startup
# 导入新的蓝图
from app.routes.vm_clone import vm_clone_bp
from app.routes.vm_management import vm_management_bp
from app.routes.vm import vm_bp
from app.routes.im_manager import im_manager_bp
from app.routes.vnc_manager import vnc_manager_bp

# 导入日志工具和全局logger
from app.utils.log_utils import logger, logging, setup_logger
from app.utils.vm_cache import vm_cache, VMStatusCache
from app.utils.im_utils import *


from flask import Blueprint, request, jsonify, render_template
from app.utils.common_utils import login_required
from app.utils.log_utils import logger
from app.utils.vm_utils import find_vmx_file_by_ip, read_vnc_config_from_vmx, scan_scripts_from_directories
from  app.utils.vm_utils import find_vnc_session_by_ip
from  app.utils.vnc_utils import send_vnc_keys

# 创建蓝图
# 创建蓝图
ssh_utils_bp = Blueprint('ssh_utils', __name__)



@ssh_utils_bp.route('/api/ssh_trust', methods=['POST'])
@login_required
def api_ssh_trust():
    """设置SSH互信"""
    logger.info("收到SSH互信设置API请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        username = data.get('username', vm_username)
        password = data.get('password', '123456')

        logger.debug(f"SSH互信参数 - 虚拟机: {vm_name}, 用户: {username}")

        if not vm_name:
            logger.warning("虚拟机名称不能为空")
            return jsonify({'success': False, 'message': '虚拟机名称不能为空'})

        logger.info(f"开始为虚拟机 {vm_name} 设置SSH互信")

        # 获取虚拟机IP地址（不执行强制重启）
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            logger.error(f"无法获取虚拟机 {vm_name} 的IP地址")
            return jsonify({'success': False, 'message': '无法获取虚拟机IP地址，请先启动虚拟机'})

        logger.debug(f"虚拟机IP: {vm_ip}")

        # 检查IP连通性
        ip_status = check_ip_connectivity(vm_ip)
        if not ip_status['success']:
            logger.warning(f"虚拟机IP {vm_ip} 无法连接: {ip_status.get('error', '未知错误')}")
            return jsonify({'success': False, 'message': f'虚拟机IP {vm_ip} 不存活，请先启动虚拟机或检查网络状态'})

        logger.debug("IP连通性检查通过")

        # 设置SSH互信
        success, message = setup_ssh_trust(vm_ip, username, password)

        if success:
            # 清理虚拟机状态缓存，确保下次检查时获取最新状态
            vm_cache.clear_cache(vm_name, 'online_status')
            logger.info(f"SSH互信设置成功: {message}")
            return jsonify({'success': True, 'message': message})
        else:
            logger.error(f"SSH互信设置失败: {message}")
            return jsonify({'success': False, 'message': message})

    except Exception as e:
        logger.error(f"SSH互信设置异常: {str(e)}")
        return jsonify({'success': False, 'message': f'设置SSH互信时发生错误: {str(e)}'})
