import os 
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from flask_socketio import SocketIO, emit
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from config import *
from app.utils.ssh_utils import SSHClient
from app.utils.vm_utils import *
from app.utils.common_utils import clear_sessions_on_startup
# 导入新的蓝图
from app.routes.vm_clone import vm_clone_bp
from app.routes.vm_management import vm_management_bp
from app.routes.vm import vm_bp
from app.routes.im_manager import im_manager_bp

# 导入日志工具和全局logger
from app.utils.log_utils import logger, logging, setup_logger
from app.utils.vm_cache import vm_cache, VMStatusCache
from app.utils.im_utils import *


from flask import Blueprint, request, jsonify, render_template
from app.utils.common_utils import *
from app.utils.log_utils import logger
from app.utils.vm_utils import *
from  app.utils.vm_utils import *
from  app.utils.vnc_utils import *

# 创建蓝图
# 创建蓝图
vnc_manager_bp = Blueprint('vnc_manager', __name__)



# VNC控制操作API
@vnc_manager_bp.route('/api/vnc_refresh', methods=['POST'])
@login_required
def api_vnc_refresh():
    """刷新VNC连接"""
    try:
        data = request.get_json()
        client_ip = data.get('client_ip')

        if not client_ip:
            return jsonify({'success': False, 'message': '缺少客户端IP参数'})

        # 查找对应的VMX文件
        vmx_file = find_vmx_file_by_ip(client_ip)
        if not vmx_file:
            return jsonify({'success': False, 'message': f'未找到IP {client_ip} 对应的虚拟机'})

        # 重新读取VNC配置
        vnc_config = read_vnc_config_from_vmx(vmx_file)
        if not vnc_config:
            return jsonify({'success': False, 'message': 'VNC配置读取失败'})

        return jsonify({
            'success': True,
            'message': 'VNC连接已刷新',
            'vnc_config': vnc_config
        })

    except Exception as e:
        logger.error(f"刷新VNC连接失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})


@vnc_manager_bp.route('/api/vnc_send_keys', methods=['POST'])
@login_required
def api_vnc_send_keys():
    """发送特殊按键组合到VNC"""
    try:
        data = request.get_json()
        client_ip = data.get('client_ip')
        key_combination = data.get('key_combination')

        if not client_ip or not key_combination:
            return jsonify({'success': False, 'message': '缺少必要参数'})

        # 查找对应的VMX文件
        vmx_file = find_vnc_session_by_ip(client_ip)
        if not vmx_file:
            return jsonify({'success': False, 'message': f'未找到IP {client_ip} 对应的VNC会话'})

        # 通过Socket.IO发送按键事件
        socketio.emit('vnc_send_keys', {
            'client_ip': client_ip,
            'key_combination': key_combination
        })

        return jsonify({
            'success': True,
            'message': f'已发送按键组合: {key_combination}'
        })

    except Exception as e:
        logger.error(f"发送VNC按键失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})


@vnc_manager_bp.route('/api/vnc/connect', methods=['POST'])
@login_required
def api_vnc_connect():
    """VNC连接API - 使用websockify + noVNC方案"""
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        client_ip = data.get('client_ip')

        # 优先使用vm_name，如果没有则使用client_ip查找虚拟机名称
        if not vm_name and client_ip:
            # 通过client_ip查找对应的虚拟机名称
            vmx_file = find_vmx_file_by_ip(client_ip)
            if vmx_file:
                # 从VMX文件路径中提取虚拟机名称
                vm_name = os.path.basename(os.path.dirname(vmx_file))
                logger.info(f"通过client_ip {client_ip} 找到虚拟机名称: {vm_name}")

        if not vm_name:
            return jsonify({'success': False, 'message': '虚拟机名称不能为空，请提供vm_name或有效的client_ip'})

        # logger.info(f"=== VNC连接请求开始 ===")
        # logger.info(f"请求连接的虚拟机名称: {vm_name}")

        # 查找对应的VMX文件
        vmx_file = find_vmx_file_by_name(vm_name)
        if not vmx_file:
            logger.warning(f"未找到虚拟机名称 {vm_name} 对应的VMX文件")
            logger.info(f"=== VNC连接请求结束 (失败: 未找到VMX文件) ===")
            return jsonify({'success': False, 'message': f'未找到虚拟机名称 {vm_name} 对应的虚拟机配置文件'})
        # 读取VNC配置
        vnc_config = read_vnc_config_from_vmx(vmx_file)
        if not vnc_config:
            logger.warning(f"VMX文件 {vmx_file} 中未找到VNC配置")
            logger.info(f"=== VNC连接请求结束 (失败: 无VNC配置) ===")
            return jsonify({'success': False, 'message': '虚拟机未启用VNC或配置不完整'})

        logger.info(f"VNC配置信息:")
        logger.info(f"  - VNC端口: {vnc_config['port']}")
        # logger.info(f"  - VNC密码: {'已设置' if vnc_config['password'] else '未设置'}")
        
        # 获取虚拟机IP地址
        client_ip = get_vm_ip_from_vmx(vmx_file)
        if not client_ip:
            logger.error(f"无法获取虚拟机IP地址")
            logger.info(f"=== VNC连接请求结束 (失败: 无法获取虚拟机IP) ===")
            return jsonify({'success': False, 'message': '无法获取虚拟机IP地址'})
        
        logger.info(f"  - 虚拟机IP: {client_ip}")

        # 启动websockify进程
        websocket_port = start_websockify(vm_name, vnc_config['port'])
        if not websocket_port:
            logger.error(f"websockify启动失败")
            logger.info(f"=== VNC连接请求结束 (失败: websockify启动失败) ===")
            return jsonify({'success': False, 'message': 'websockify启动失败'})

        logger.info(f"websockify启动成功:")
        # logger.info(f"  - 客户端IP: {client_ip}")
        # logger.info(f"  - 虚拟机名称: {vm_name}")
        # logger.info(f"  - VMX文件: {vmx_file}")
        # #logger.info(f"  - VNC端口: {vnc_config['port']}")
        # logger.info(f"  - WebSocket端口: {websocket_port}")
        logger.info(f"=== VNC连接请求结束 (成功) ===")

        return jsonify({
            'success': True,
            'vnc_config': {
                'host': 'localhost',
                'vnc_port': vnc_config['port'],
                'websocket_port': websocket_port,
                'password': vnc_config['password'],
                'vmx_file': vmx_file
            }
        })

    except Exception as e:
        logger.error(f"VNC连接失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})



# VNC断开连接API
@vnc_manager_bp.route('/api/vnc/disconnect', methods=['POST'])
@login_required
def api_vnc_disconnect():
    """断开VNC连接"""
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')

        if not vm_name:
            return jsonify({'success': False, 'message': '虚拟机名称不能为空'})

        # 查找对应的VMX文件以获取IP
        vmx_file = find_vmx_file_by_name(vm_name)
        if not vmx_file:
            logger.warning(f"未找到虚拟机名称 {vm_name} 对应的VMX文件")
            return jsonify({'success': False, 'message': f'未找到虚拟机名称 {vm_name} 对应的虚拟机配置文件'})
        
        # 获取虚拟机IP地址
        client_ip = get_vm_ip_from_vmx(vmx_file)
        if not client_ip:
            logger.warning(f"无法获取虚拟机 {vm_name} 的IP地址")
        # 统一使用stop_websockify_by_vm_name函数停止进程
        stop_websockify_by_vm_name(vm_name)

        return jsonify({'success': True, 'message': 'VNC连接已断开'})

    except Exception as e:
        logger.error(f"断开VNC连接失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})


# 清理所有VNC连接API
@vnc_manager_bp.route('/api/vnc/cleanup_all', methods=['POST'])
@login_required
def api_vnc_cleanup_all():
    """清理所有VNC连接和websockify进程"""
    try:
        success = cleanup_all_vnc_connections()

        if success:
            return jsonify({'success': True, 'message': '所有VNC连接和进程已清理完成'})
        else:
            return jsonify({'success': False, 'message': '清理过程中出现部分错误，请检查日志'})

    except Exception as e:
        logger.error(f"清理所有VNC连接失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})
