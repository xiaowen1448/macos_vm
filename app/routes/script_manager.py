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
from app.utils.vm_utils import find_vmx_file_by_ip, scan_scripts_from_directories

# 创建蓝图
# 创建蓝图
script_manager_bp = Blueprint('script_manager', __name__)


@script_manager_bp.route('/api/scripts')
@login_required
def api_scripts():
    """获取脚本文件列表（支持分页）"""
    # logger.info("收到获取脚本列表请求")
    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 5, type=int)  # 修改默认分页大小为5

        logger.info(f"收到分页请求: page={page}, page_size={page_size}")
        logger.info(f"请求参数: {dict(request.args)}")

        # 使用新的通用脚本扫描函数
        scripts = scan_scripts_from_directories()

        # 计算分页信息
        total_count = len(scripts)
        total_pages = (total_count + page_size - 1) // page_size
        start_index = (page - 1) * page_size
        end_index = min(start_index + page_size, total_count)

        # 获取当前页的数据
        current_page_scripts = scripts[start_index:end_index]

        # 确保end_index反映实际返回的数据数量
        actual_end_index = start_index + len(current_page_scripts)

        logger.info(f"分页计算详情: total_count={total_count}, page_size={page_size}, page={page}")
        logger.info(f"分页索引: start_index={start_index}, end_index={end_index}, actual_end_index={actual_end_index}")
        logger.info(f"当前页脚本数量: {len(current_page_scripts)}")
        logger.info(f"脚本文件名列表: {[script['name'] for script in current_page_scripts]}")
        logger.info(f"成功获取 {len(current_page_scripts)} 个脚本文件（第 {page} 页，共 {total_pages} 页）")
        logger.info(
            f"返回的pagination数据: {{'current_page': {page}, 'page_size': {page_size}, 'total_count': {total_count}, 'total_pages': {total_pages}, 'start_index': {start_index}, 'end_index': {actual_end_index}}}")
        return jsonify({
            'success': True,
            'scripts': current_page_scripts,
            'pagination': {
                'current_page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': total_pages,
                'start_index': start_index,
                'end_index': actual_end_index
            }
        })

    except Exception as e:
        logger.error(f"获取脚本列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取脚本列表失败: {str(e)}'
        })


@script_manager_bp.route('/api/scripts/all')
@login_required
def api_all_scripts():
    """获取所有脚本文件列表（不分页）"""
    # logger.info("收到获取所有脚本列表请求")
    try:
        # 使用新的通用脚本扫描函数
        scripts = scan_scripts_from_directories()

      ##  logger.info(f"成功获取 {len(scripts)} 个脚本文件")
        return jsonify({
            'success': True,
            'scripts': scripts
        })

    except Exception as e:
        logger.error(f"获取所有脚本列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取所有脚本列表失败: {str(e)}'
        })


@script_manager_bp.route('/api/script/add', methods=['POST'])
@login_required
def api_add_script():
    """新增脚本内容和备注"""
    logger.info("收到新增脚本请求")
    try:
        data = request.get_json()
        script_name = data.get('script_name')
        content = data.get('content')
        note = data.get('note', '')

        if not script_name or content is None:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            })

        # 检查文件名是否以.sh结尾
        if not script_name.endswith('.sh'):
            return jsonify({
                'success': False,
                'message': '脚本文件名必须以.sh结尾'
            })

        # 检查是否包含中文字符

        if re.search(r'[\u4e00-\u9fa5]', script_name):
            return jsonify({
                'success': False,
                'message': '脚本文件名不能包含中文字符'
            })

        # 检查文件名是否只包含合法字符（字母、数字、下划线、连字符、点）
        if not re.match(r'^[a-zA-Z0-9_.-]+\.sh$', script_name):
            return jsonify({
                'success': False,
                'message': '脚本文件名只能包含字母、数字、下划线、连字符和点，且必须以.sh结尾'
            })

        # 使用配置的第一个脚本目录（.sh脚本目录）
        scripts_dir = script_upload_dirs[0]  # D:\macos_vm\macos_script\macos_sh
        script_path = os.path.join(scripts_dir, script_name)
        note_path = script_path.replace('.sh', '.txt')

        # 检查文件是否已存在
        if os.path.exists(script_path):
            return jsonify({
                'success': False,
                'message': f'脚本文件已存在: {script_name}'
            })

        # 保存脚本内容
        try:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"脚本内容已创建: {script_name}")
        except Exception as e:
            logger.error(f"创建脚本内容失败: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'创建脚本内容失败: {str(e)}'
            })

        # 保存备注
        try:
            with open(note_path, 'w', encoding='utf-8') as f:
                f.write(note)
            logger.info(f"脚本备注已创建: {script_name}")
        except Exception as e:
            logger.error(f"创建脚本备注失败: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'创建脚本备注失败: {str(e)}'
            })

        return jsonify({
            'success': True,
            'message': '脚本新增成功'
        })

    except Exception as e:
        logger.error(f"新增脚本失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'新增脚本失败: {str(e)}'
        })


@script_manager_bp.route('/api/script/edit', methods=['POST'])
@login_required
def api_edit_script():
    """编辑脚本内容和备注"""
    logger.info("收到编辑脚本请求")
    try:
        data = request.get_json()
        script_name = data.get('script_name')
        content = data.get('content')
        note = data.get('note', '')

        if not script_name or content is None:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            })

        # 从配置的多个目录中查找脚本文件
        script_path = None
        for script_dir in script_upload_dirs:
            potential_path = os.path.join(script_dir, script_name)
            if os.path.exists(potential_path):
                script_path = potential_path
                break

        if not script_path:
            return jsonify({
                'success': False,
                'message': f'脚本文件不存在: {script_name}'
            })

        note_path = script_path.replace('.sh', '.txt').replace('.scpt', '.txt')

        # 保存脚本内容
        try:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"脚本内容已保存: {script_name}")
        except Exception as e:
            logger.error(f"保存脚本内容失败: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'保存脚本内容失败: {str(e)}'
            })

        # 保存备注
        try:
            with open(note_path, 'w', encoding='utf-8') as f:
                f.write(note)
            logger.info(f"脚本备注已保存: {script_name}")
        except Exception as e:
            logger.error(f"保存脚本备注失败: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'保存脚本备注失败: {str(e)}'
            })

        return jsonify({
            'success': True,
            'message': '脚本编辑成功'
        })

    except Exception as e:
        logger.error(f"编辑脚本失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'编辑脚本失败: {str(e)}'
        })


@script_manager_bp.route('/api/script/delete', methods=['POST'])
@login_required
def api_delete_script():
    """删除脚本文件"""
    logger.info("收到删除脚本请求")
    try:
        data = request.get_json()
        script_name = data.get('script_name')

        if not script_name:
            return jsonify({
                'success': False,
                'message': '缺少脚本名称参数'
            })

        # 验证脚本名称格式
        if not script_name.endswith('.sh'):
            return jsonify({
                'success': False,
                'message': '脚本文件名必须以.sh结尾'
            })

        # 检查是否包含中文字符
        if any('\u4e00' <= char <= '\u9fff' for char in script_name):
            return jsonify({
                'success': False,
                'message': '脚本名称不能包含中文字符'
            })

        # 从配置的多个目录中查找脚本文件
        script_path = None
        for script_dir in script_upload_dirs:
            potential_path = os.path.join(script_dir, script_name)
            if os.path.exists(potential_path):
                script_path = potential_path
                break

        if not script_path:
            return jsonify({
                'success': False,
                'message': f'脚本文件不存在: {script_name}'
            })

        note_path = script_path.replace('.sh', '.txt').replace('.scpt', '.txt')

        try:
            # 删除脚本文件
            os.remove(script_path)
            logger.info(f"删除脚本文件: {script_path}")

            # 如果存在对应的备注文件，也一并删除
            if os.path.exists(note_path):
                os.remove(note_path)
                logger.info(f"删除备注文件: {note_path}")

            return jsonify({
                'success': True,
                'message': f'脚本 {script_name} 删除成功'
            })

        except Exception as e:
            logger.error(f"删除脚本文件失败: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'删除脚本文件失败: {str(e)}'
            })

    except Exception as e:
        logger.error(f"删除脚本失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除脚本失败: {str(e)}'
        })


@script_manager_bp.route('/api/script/content/<script_name>')
@login_required
def api_get_script_content(script_name):
    """获取脚本内容"""
    logger.info(f"获取脚本内容: {script_name}")
    try:
        # 从配置的多个目录中查找脚本文件
        script_path = None
        for script_dir in script_upload_dirs:
            potential_path = os.path.join(script_dir, script_name)
            if os.path.exists(potential_path):
                script_path = potential_path
                break

        if not script_path:
            return jsonify({
                'success': False,
                'message': f'脚本文件不存在: {script_name}'
            })

        note_path = script_path.replace('.sh', '.txt').replace('.scpt', '.txt')

        # 读取脚本内容
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"读取脚本内容失败: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'读取脚本内容失败: {str(e)}'
            })

        # 读取备注
        note = ""
        if os.path.exists(note_path):
            try:
                with open(note_path, 'r', encoding='utf-8') as f:
                    note = f.read().strip()
            except Exception as e:
                logger.warning(f"读取备注文件失败: {str(e)}")

        return jsonify({
            'success': True,
            'content': content,
            'note': note
        })

    except Exception as e:
        logger.error(f"获取脚本内容失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取脚本内容失败: {str(e)}'
        })


@script_manager_bp.route('/api/vm_send_script', methods=['POST'])
@login_required
def api_vm_send_script():
    """发送脚本到指定虚拟机（仅发送，不添加权限）"""
    logger.info("收到发送脚本到虚拟机请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        script_name = data.get('script_name')

        if not vm_name or not script_name:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            })

        # 从配置的多个目录中查找脚本文件
        script_path = None
        for script_dir in script_upload_dirs:
            potential_path = os.path.join(script_dir, script_name)
            if os.path.exists(potential_path):
                script_path = potential_path
                break

        if not script_path:
            return jsonify({
                'success': False,
                'message': f'脚本文件不存在: {script_name}'
            })

        # 检查虚拟机状态和SSH互信
        try:
            vm_info = get_vm_online_status(vm_name)

            if vm_info['status'] != 'online' or not vm_info.get('ssh_trust', False):
                return jsonify({
                    'success': False,
                    'message': f'虚拟机 {vm_name} 未在线或未建立SSH互信'
                })

            # 使用scp发送脚本，sh=> macos_sh目录，scpt=>macos_scpt
            if script_name.endswith('.sh'):
                file_script_remote_path = f"{sh_script_remote_path}"
            else:
                file_script_remote_path = f"{scpt_script_remote_path}"

            # 使用SFTP发送脚本
            remote_file_path = f"{file_script_remote_path}{script_name}"
            success, message = send_file_via_sftp(script_path, remote_file_path, vm_info['ip'], vm_username, timeout=30)

            if success:
                logger.info(f"脚本发送成功到虚拟机 {vm_name} ({vm_info['ip']})")
                return jsonify({
                    'success': True,
                    'message': f'脚本 {script_name} 发送成功到虚拟机 {vm_name}',
                    'file_path': remote_file_path
                })
            else:
                logger.error(f"脚本发送失败到虚拟机 {vm_name}: {message}")

                # 根据错误类型提供更详细的错误信息
                if 'Permission denied' in message:
                    error_detail = 'SSH认证失败，请检查SSH互信设置'
                elif 'Connection refused' in message:
                    error_detail = 'SSH连接被拒绝，请检查SSH服务是否运行'
                elif 'No route to host' in message:
                    error_detail = '无法连接到主机，请检查网络连接'
                else:
                    error_detail = message

                return jsonify({
                    'success': False,
                    'message': error_detail
                })

        except subprocess.TimeoutExpired:
            logger.error(f"发送脚本到虚拟机 {vm_name} 超时")
            return jsonify({
                'success': False,
                'message': 'SCP传输超时（30秒）'
            })
        except Exception as e:
            logger.error(f"发送脚本到虚拟机 {vm_name} 时出错: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'发送出错: {str(e)}'
            })

    except Exception as e:
        logger.error(f"发送脚本到虚拟机失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'发送脚本失败: {str(e)}'
        })


@script_manager_bp.route('/api/vm_add_permissions', methods=['POST'])
@login_required
def api_vm_add_permissions():
    """为虚拟机上的脚本添加执行权限"""
    logger.info("收到添加脚本执行权限API请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        script_names = data.get('script_names', [])
        username = data.get('username', vm_username)
        if not vm_name:
            logger.warning("虚拟机名称不能为空")
            return jsonify({'success': False, 'message': '虚拟机名称不能为空'})

        if not script_names or len(script_names) == 0:
            logger.warning("脚本名称列表不能为空")
            return jsonify({'success': False, 'message': '脚本名称列表不能为空'})

        logger.info(f"开始为虚拟机 {vm_name} 的脚本添加执行权限")

        # 获取虚拟机IP地址（不执行强制重启）
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            logger.error(f"无法获取虚拟机 {vm_name} 的IP地址")
            return jsonify({'success': False, 'message': '无法获取虚拟机IP地址，请确保虚拟机正在运行'})

        logger.debug(f"虚拟机IP: {vm_ip}")

        # 检查IP连通性
        ip_status = check_ip_connectivity(vm_ip)
        if not ip_status['success']:
            logger.warning(f"虚拟机IP {vm_ip} 无法连接: {ip_status.get('error', '未知错误')}")
            return jsonify({'success': False, 'message': f'虚拟机IP {vm_ip} 不存活，请先启动虚拟机'})

        logger.debug("IP连通性检查通过")

        # 检查SSH互信状态
        ssh_trust_status = check_ssh_trust_status(vm_ip, username)
        if not ssh_trust_status:
            logger.warning(f"SSH互信未建立")
            return jsonify({'success': False, 'message': f'SSH互信未建立，请先设置SSH互信'})

        logger.debug("SSH互信检查通过")

        # 执行chmod命令
        success, message = execute_chmod_scripts(vm_ip, username, script_names)

        if success:
            logger.info(f"脚本执行权限设置成功: {message}")
            return jsonify({'success': True, 'message': message})
        else:
            logger.error(f"脚本执行权限设置失败: {message}")
            return jsonify({'success': False, 'message': message})

    except Exception as e:
        logger.error(f"添加脚本执行权限异常: {str(e)}")
        return jsonify({'success': False, 'message': f'添加脚本执行权限时发生错误: {str(e)}'})




@script_manager_bp.route('/api/vm_chmod_scripts', methods=['POST'])
@login_required
def api_vm_chmod_scripts():
    """为虚拟机上的指定脚本或所有sh脚本添加执行权限"""
    logger.info("收到为脚本添加执行权限API请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        script_names = data.get('script_names', [])  # 可以传入单个脚本名或脚本名列表
        username = data.get('username', vm_username)

        if not vm_name:
            logger.warning("虚拟机名称不能为空")
            return jsonify({'success': False, 'message': '虚拟机名称不能为空'})

        logger.info(f"开始为虚拟机 {vm_name} 的脚本添加执行权限")

        # 获取虚拟机IP地址
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            logger.error(f"无法获取虚拟机 {vm_name} 的IP地址")
            return jsonify({'success': False, 'message': '无法获取虚拟机IP地址，请确保虚拟机正在运行'})

        logger.debug(f"虚拟机IP: {vm_ip}")

        # 检查IP连通性
        ip_status = check_ip_connectivity(vm_ip)
        if not ip_status['success']:
            logger.warning(f"虚拟机IP {vm_ip} 无法连接: {ip_status.get('error', '未知错误')}")
            return jsonify({'success': False, 'message': f'虚拟机IP {vm_ip} 无法连接，请检查网络状态'})

        logger.debug("IP连通性检查通过")

        # 检查SSH互信状态
        ssh_trust_status = check_ssh_trust_status(vm_ip, username)
        if not ssh_trust_status:
            logger.warning(f"SSH互信未建立")
            return jsonify({'success': False, 'message': f'SSH互信未建立，请先设置SSH互信'})

        logger.debug("SSH互信检查通过")

        # 执行chmod命令
        success, message = execute_chmod_scripts(vm_ip, username, script_names)

        if success:
            logger.info(f"脚本执行权限设置成功: {message}")
            return jsonify({'success': True, 'message': message})
        else:
            logger.error(f"脚本执行权限设置失败: {message}")
            return jsonify({'success': False, 'message': message})

    except Exception as e:
        logger.error(f"添加脚本执行权限异常: {str(e)}")
        return jsonify({'success': False, 'message': f'添加脚本执行权限时发生错误: {str(e)}'})


@script_manager_bp.route('/api/vm_chengpin_execute_scripts', methods=['POST'])
@login_required
def api_vm_chengpin_execute_scripts():
    """批量执行脚本在成品虚拟机上"""
    logger.info("收到批量执行脚本在成品虚拟机请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        script_names = data.get('script_names', [])

        if not vm_name or not script_names:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称或脚本名称列表参数'
            })

        # 检查虚拟机状态和SSH互信
        vm_info = get_vm_online_status(vm_name)

        if vm_info['status'] != 'online' or not vm_info.get('ssh_trust', False):
            return jsonify({
                'success': False,
                'message': f'虚拟机 {vm_name} 未在线或未建立SSH互信'
            })

        # 批量执行远程脚本
        results = {}
        for script_name in script_names:
            result = execute_remote_script(vm_info['ip'], 'wx', script_name)

            if len(result) == 3:
                success, output, full_log = result
                error = ""
            elif len(result) == 4:
                success, output, error, full_log = result
            else:
                success, output, error, full_log = False, "", "未知错误", ""

            results[script_name] = {
                'success': success,
                'output': output,
                'error': error,
                'ssh_log': full_log
            }

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        logger.error(f"批量执行脚本在成品虚拟机失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量执行脚本失败: {str(e)}'
        })


@script_manager_bp.route('/api/vm_chengpin_chmod_scripts', methods=['POST'])
@login_required
def api_vm_chengpin_chmod_scripts():
    """为成品虚拟机脚本添加执行权限"""
    logger.info("收到为成品虚拟机脚本添加执行权限请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        script_names = data.get('script_names', [])
        username = data.get('username', vm_username)

        if not vm_name or not script_names:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称或脚本名称列表参数'
            })

        # 获取虚拟机IP（不执行强制重启）
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            return jsonify({
                'success': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址，请先启动虚拟机'
            })

        # 检查IP连通性
        if not check_ip_connectivity(vm_ip):
            return jsonify({
                'success': False,
                'message': f'虚拟机IP {vm_ip} 不存活，请先启动虚拟机或检查网络状态'
            })

        # 添加执行权限
        success, message = execute_chmod_scripts(vm_ip, username, script_names)

        return jsonify({
            'success': True,
            'message': message
        })
    except Exception as e:
        logger.error(f"为成品虚拟机脚本添加执行权限失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'为成品虚拟机脚本添加执行权限失败: {str(e)}'
        })


@script_manager_bp.route('/api/vm_chengpin_execute_script', methods=['POST'])
@login_required
def api_vm_chengpin_execute_script():
    """执行脚本在成品虚拟机上"""
    logger.info("收到执行脚本在成品虚拟机请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        script_name = data.get('script_name')

        if not vm_name or not script_name:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称或脚本名称参数'
            })

        # 检查虚拟机状态和SSH互信
        vm_info = get_vm_online_status(vm_name)

        if vm_info['status'] != 'online' or not vm_info.get('ssh_trust', False):
            return jsonify({
                'success': False,
                'message': f'虚拟机 {vm_name} 未在线或未建立SSH互信'
            })

        # 执行远程脚本
        logger.info(f"开始执行脚本 {script_name} 在成品虚拟机 {vm_name} ({vm_info['ip']})")
        result = execute_remote_script(vm_info['ip'], 'wx', script_name)

        logger.info(f"execute_remote_script 返回结果: {result}")

        if len(result) == 3:
            success, output, full_log = result
            error = ""
        elif len(result) == 4:
            success, output, error, full_log = result
        else:
            success, output, error, full_log = False, "", "未知错误", ""

        logger.info(
            f"处理后的结果: success={success}, output_length={len(output) if output else 0}, error={error}, log_length={len(full_log) if full_log else 0}")

        response_data = {
            'success': success,
            'output': output,
            'error': error,
            'ssh_log': full_log
        }

        logger.info(f"返回响应: {response_data}")
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"执行脚本在成品虚拟机失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'执行脚本失败: {str(e)}'
        })



@script_manager_bp.route('/api/vm_10_12_chmod_scripts', methods=['POST'])
@login_required
def api_vm_10_12_chmod_scripts():
    """为10.12目录虚拟机脚本添加执行权限"""
    logger.info("收到为10.12目录虚拟机脚本添加执行权限请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        script_names = data.get('script_names', [])
        username = data.get('username', vm_username)

        if not vm_name or not script_names:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称或脚本名称列表参数'
            })

        # 获取虚拟机IP
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            return jsonify({
                'success': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址'
            })

        # 添加执行权限
        success, message = execute_chmod_scripts(vm_ip, username, script_names)

        return jsonify({
            'success': True,
            'message': message
        })
    except Exception as e:
        logger.error(f"为10.12目录虚拟机脚本添加执行权限失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'为10.12目录虚拟机脚本添加执行权限失败: {str(e)}'
        })


@script_manager_bp.route('/api/vm_10_12_execute_script', methods=['POST'])
@login_required
def api_vm_10_12_execute_script():
    """执行脚本在10.12目录虚拟机上"""
    logger.info("收到执行脚本在10.12目录虚拟机请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        script_name = data.get('script_name')

        if not vm_name or not script_name:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称或脚本名称参数'
            })

        # 检查虚拟机状态和SSH互信
        vm_info = get_vm_online_status(vm_name)

        if vm_info['status'] != 'online' or not vm_info.get('ssh_trust', False):
            return jsonify({
                'success': False,
                'message': f'虚拟机 {vm_name} 未在线或未建立SSH互信'
            })

        # 执行远程脚本
        logger.info(f"开始执行脚本 {sh_script_remote_path}{script_name} 在虚拟机 {vm_name} ({vm_info['ip']})")
        result = execute_remote_script(vm_info['ip'], 'wx', f'{sh_script_remote_path}{script_name}')

        logger.info(f"execute_remote_script 返回结果: {result}")

        if len(result) == 3:
            success, output, full_log = result
            error = ""
        elif len(result) == 4:
            success, output, error, full_log = result
        else:
            success, output, error, full_log = False, "", "未知错误", ""

        logger.info(
            f"处理后的结果: success={success}, output_length={len(output) if output else 0}, error={error}, log_length={len(full_log) if full_log else 0}")

        response_data = {
            'success': success,
            'output': output,
            'error': error,
            'ssh_log': full_log
        }

        logger.info(f"返回响应: {response_data}")
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"执行脚本在10.12目录虚拟机失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'执行脚本失败: {str(e)}'
        })


@script_manager_bp.route('/api/vm_10_12_execute_scripts', methods=['POST'])
@login_required
def api_vm_10_12_execute_scripts():
    """批量执行脚本在10.12目录虚拟机上"""
    logger.info("收到批量执行脚本在10.12目录虚拟机请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        script_names = data.get('script_names', [])

        if not vm_name or not script_names:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称或脚本名称列表参数'
            })

        # 检查虚拟机状态和SSH互信
        vm_info = get_vm_online_status(vm_name)

        if vm_info['status'] != 'online' or not vm_info.get('ssh_trust', False):
            return jsonify({
                'success': False,
                'message': f'虚拟机 {vm_name} 未在线或未建立SSH互信'
            })

        # 批量执行远程脚本
        results = {}
        for script_name in script_names:
            result = execute_remote_script(vm_info['ip'], 'wx', script_name)

            if len(result) == 3:
                success, output, full_log = result
                error = ""
            elif len(result) == 4:
                success, output, error, full_log = result
            else:
                success, output, error, full_log = False, "", "未知错误", ""

            results[script_name] = {
                'success': success,
                'output': output,
                'error': error,
                'ssh_log': full_log
            }

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        logger.error(f"批量执行脚本在10.12目录虚拟机失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量执行脚本失败: {str(e)}'
        })