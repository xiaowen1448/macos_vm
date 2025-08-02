import json
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from functools import wraps
import os
import datetime
import uuid
import threading
import time
import subprocess
import paramiko
import base64
import sys

from config import *

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('app_debug.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # 用于会话加密

# 设置Flask应用的日志级别
app.logger.setLevel(logging.DEBUG)

# 添加请求日志中间件
@app.before_request
def log_request_info():
    logger.info(f"收到请求: {request.method} {request.url}")
    logger.debug(f"请求头: {dict(request.headers)}")
    if request.method == 'POST':
        logger.debug(f"POST数据: {request.get_data(as_text=True)}")

@app.after_request
def log_response_info(response):
    logger.info(f"响应状态: {response.status_code}")
    return response

# 使用全局配置文件中的认证信息
# USERNAME and PASSWORD are imported from config.py

# 虚拟机目录配置 - 使用全局配置
VM_DIRS = {
    '10_12': clone_dir,
    'chengpin': vm_chengpin_dir
}

# 模板虚拟机路径 - 使用全局配置
# template_dir is imported from config.py

# 全局任务存储
clone_tasks = {}
tasks = {}

def get_vmrun_path():
    """获取vmrun路径，优先使用配置文件中的路径，如果不存在则使用备用路径"""
    if os.path.exists(vmrun_path):
        return vmrun_path
    else:
        backup_path = r'C:\Program Files\VMware\VMware Workstation\vmrun.exe'
        if os.path.exists(backup_path):
            return backup_path
        else:
            raise FileNotFoundError(f"vmrun.exe not found at {vmrun_path} or {backup_path}")

# 通用函数 - 获取虚拟机列表
def get_vm_list_from_directory(vm_dir, vm_type_name):
    """从指定目录获取虚拟机列表"""
    logger.info(f"收到获取{vm_type_name}虚拟机列表API请求")
    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        logger.debug(f"分页参数 - 页码: {page}, 每页大小: {page_size}")
        
        vms = []
        stats = {'total': 0, 'running': 0, 'stopped': 0, 'online': 0}
        
        logger.debug(f"开始扫描{vm_type_name}虚拟机目录: {vm_dir}")
        
        # 批量获取运行中的虚拟机列表（只执行一次vmrun命令）
        running_vms = set()
        try:
            vmrun_path = get_vmrun_path()
            
            list_cmd = [vmrun_path, 'list']
            logger.debug(f"执行vmrun命令: {list_cmd}")
            result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                running_vms = set(result.stdout.strip().split('\n')[1:])  # 跳过标题行
                logger.debug(f"获取到运行中虚拟机: {len(running_vms)} 个")
            else:
                logger.warning(f"vmrun命令执行失败: {result.stderr}")
        except Exception as e:
            logger.error(f"获取运行中虚拟机列表失败: {str(e)}")
        
        if os.path.exists(vm_dir):
            for root, dirs, files in os.walk(vm_dir):
                for file in files:
                    if file.endswith('.vmx'):
                        vm_path = os.path.join(root, file)
                        vm_name = os.path.splitext(file)[0]
                        
                        # 快速判断虚拟机状态（基于文件名匹配）
                        vm_status = 'stopped'
                        for running_vm in running_vms:
                            if vm_name in running_vm:
                                vm_status = 'running'
                                break
                        
                        logger.debug(f"找到{vm_type_name}虚拟机: {vm_name}, 状态: {vm_status}")
                        
                        # 构建虚拟机基本信息
                        vm_info = {
                            'name': vm_name,
                            'path': vm_path,
                            'status': vm_status,
                            'online_status': 'unknown',  # 初始状态为未知
                            'online_reason': '',
                            'ip': '获取中...' if vm_status == 'running' else '-',
                            'ssh_trust': False,
                            'wuma_info': get_wuma_info(vm_name) or '未配置',
                            'ju_info': '未获取到ju值信息',  # JU值信息初始状态
                            'wuma_view_status': '未获取',  # 五码查看状态初始状态
                            'ssh_status': 'unknown',
                            'vm_status': vm_status  # 添加虚拟机状态字段
                        }
                        vms.append(vm_info)
                        
                        # 更新统计信息
                        stats['total'] += 1
                        if vm_status == 'running':
                            stats['running'] += 1
                        elif vm_status == 'stopped':
                            stats['stopped'] += 1
        else:
            logger.warning(f"{vm_type_name}虚拟机目录不存在: {vm_dir}")
        
        # 对虚拟机进行排序：运行中的虚拟机排在前面
        vms.sort(key=lambda vm: (vm['status'] != 'running', vm['name']))
        
        # 计算分页
        total_count = len(vms)
        total_pages = (total_count + page_size - 1) // page_size
        start_index = (page - 1) * page_size
        end_index = min(start_index + page_size, total_count)
        
        # 分页数据
        paged_vms = vms[start_index:end_index] if vms else []
        
        logger.info(f"{vm_type_name}虚拟机列表获取完成 - 总数: {total_count}, 运行中: {stats['running']}, 已停止: {stats['stopped']}")
        
        return jsonify({
            'success': True,
            'vms': paged_vms,
            'stats': stats,
            'pagination': {
                'current_page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': total_pages,
                'start_index': start_index,
                'end_index': end_index
            }
        })
    except Exception as e:
        logger.error(f"获取{vm_type_name}虚拟机列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取{vm_type_name}虚拟机列表失败: {str(e)}'
        })

# 通用函数 - 获取五码信息
def get_wuma_info_generic(vm_type_name):
    """获取虚拟机五码信息的通用函数"""
    logger.info(f"收到获取{vm_type_name}虚拟机五码信息请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        
        if not vm_name:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称参数'
            })
        
        # 获取虚拟机IP
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            return jsonify({
                'success': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址'
            })
        
        # 执行远程脚本获取五码信息
        result = execute_remote_script(vm_ip, 'wx', 'run_debug_wuma.sh')
        if len(result) == 3:
            success, output, ssh_log = result
        elif len(result) == 2:
            success, output = result
        else:
            success, output = False, "未知错误"
        
        if success:
            return jsonify({
                'success': True,
                'output': output
            })
        else:
            return jsonify({
                'success': False,
                'error': output
            })
    except Exception as e:
        logger.error(f"获取{vm_type_name}虚拟机五码信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取{vm_type_name}虚拟机五码信息失败: {str(e)}'
        })

# 通用函数 - 获取JU值信息
def get_ju_info_generic(vm_type_name):
    """获取虚拟机JU值信息的通用函数"""
    logger.info(f"收到获取{vm_type_name}虚拟机JU值信息请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        
        if not vm_name:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称参数'
            })
        
        # 获取虚拟机IP
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            return jsonify({
                'success': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址'
            })
        
        # 执行远程脚本获取JU值信息
        result = execute_remote_script(vm_ip, 'wx', 'run_debug_ju.sh')
        if len(result) == 3:
            success, output, ssh_log = result
        elif len(result) == 2:
            success, output = result
        else:
            success, output = False, "未知错误"
        
        if success:
            return jsonify({
                'success': True,
                'output': output
            })
        else:
            return jsonify({
                'success': False,
                'error': output
            })
    except Exception as e:
        logger.error(f"获取{vm_type_name}虚拟机JU值信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取{vm_type_name}虚拟机JU值信息失败: {str(e)}'
        })

# 通用函数 - 虚拟机操作（启动、停止、重启）
def vm_operation_generic(operation, vm_type_name, vm_dir):
    """虚拟机操作的通用函数"""
    logger.info(f"收到{operation}{vm_type_name}虚拟机请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        
        if not vm_name:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称参数'
            })
        
        # 查找虚拟机文件
        vm_file = find_vm_file(vm_name)
        if not vm_file:
            return jsonify({
                'success': False,
                'message': f'虚拟机 {vm_name} 文件不存在'
            })
        
        # 检查是否在指定目录中
        if not vm_file.startswith(vm_dir):
            return jsonify({
                'success': False,
                'message': f'虚拟机 {vm_name} 不在{vm_type_name}目录中'
            })
        
        # 执行虚拟机操作
        vmrun_path = get_vmrun_path()
        
        if operation == 'start':
            cmd = [vmrun_path, 'start', vm_file, 'nogui']
        elif operation == 'stop':
            cmd = [vmrun_path, 'stop', vm_file, 'hard']
        elif operation == 'restart':
            cmd = [vmrun_path, 'reset', vm_file, 'hard']
        else:
            return jsonify({
                'success': False,
                'message': f'不支持的操作: {operation}'
            })
        
        logger.info(f"执行{operation}命令: {cmd}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            logger.info(f"{vm_type_name}虚拟机 {vm_name} {operation}成功")
            return jsonify({
                'success': True,
                'message': f'{vm_type_name}虚拟机 {vm_name} {operation}成功'
            })
        else:
            logger.error(f"{vm_type_name}虚拟机 {vm_name} {operation}失败: {result.stderr}")
            return jsonify({
                'success': False,
                'message': f'{vm_type_name}虚拟机 {vm_name} {operation}失败: {result.stderr}'
            })
    except Exception as e:
        logger.error(f"{operation}{vm_type_name}虚拟机失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'{operation}{vm_type_name}虚拟机失败: {str(e)}'
        })

# 通用函数 - 删除虚拟机
def delete_vm_generic(vm_type_name, vm_dir):
    """删除虚拟机的通用函数"""
    logger.info(f"收到删除{vm_type_name}虚拟机请求")
    try:
        data = request.get_json()
        vm_names = data.get('vm_names', [])
        
        if not vm_names:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称列表'
            })
        
        deleted_count = 0
        errors = []
        
        for vm_name in vm_names:
            try:
                # 查找虚拟机文件
                vm_file = find_vm_file(vm_name)
                if not vm_file:
                    errors.append(f'虚拟机 {vm_name} 文件不存在')
                    continue
                
                # 检查是否在指定目录中
                if not vm_file.startswith(vm_dir):
                    errors.append(f'虚拟机 {vm_name} 不在{vm_type_name}目录中')
                    continue
                
                # 删除虚拟机文件
                vm_dir_path = os.path.dirname(vm_file)
                if os.path.exists(vm_dir_path):
                    import shutil
                    shutil.rmtree(vm_dir_path)
                    logger.info(f"成功删除{vm_type_name}虚拟机: {vm_name}")
                    deleted_count += 1
                else:
                    errors.append(f'虚拟机目录不存在: {vm_dir_path}')
                    
            except Exception as e:
                logger.error(f"删除{vm_type_name}虚拟机 {vm_name} 失败: {str(e)}")
                errors.append(f'删除虚拟机 {vm_name} 失败: {str(e)}')
        
        if deleted_count > 0:
            message = f'成功删除 {deleted_count} 个{vm_type_name}虚拟机'
            if errors:
                message += f'，但有 {len(errors)} 个错误: ' + '; '.join(errors)
            
            # 构建详细的返回结果
            result = {
                'success': True,
                'message': message,
                'deleted_count': deleted_count,
                'error_count': len(errors),
                'deleted_vms': [],  # 成功删除的虚拟机列表
                'failed_vms': []    # 删除失败的虚拟机列表
            }
            
            # 分析成功和失败的虚拟机
            for vm_name in vm_names:
                if any(error.startswith(f'虚拟机 {vm_name}') for error in errors):
                    result['failed_vms'].append(vm_name)
                else:
                    result['deleted_vms'].append(vm_name)
            
            return jsonify(result)
        else:
            return jsonify({
                'success': False,
                'message': '删除失败: ' + '; '.join(errors),
                'deleted_count': 0,
                'error_count': len(errors),
                'deleted_vms': [],
                'failed_vms': vm_names
            })
    except Exception as e:
        logger.error(f"删除{vm_type_name}虚拟机失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除{vm_type_name}虚拟机失败: {str(e)}'
        })

# 通用函数 - 获取虚拟机详细信息
def get_vm_info_generic(vm_name, vm_type_name, vm_dir):
    """获取虚拟机详细信息的通用函数"""
    logger.info(f"收到获取{vm_type_name}虚拟机详细信息请求: {vm_name}")
    try:
        # 查找虚拟机文件
        vm_file = find_vm_file(vm_name)
        if not vm_file:
            return jsonify({
                'success': False,
                'message': f'虚拟机 {vm_name} 文件不存在'
            })
        
        # 检查是否在指定目录中
        if not vm_file.startswith(vm_dir):
            return jsonify({
                'success': False,
                'message': f'虚拟机 {vm_name} 不在{vm_type_name}目录中'
            })
        
        # 获取虚拟机状态
        vm_status = get_vm_status(vm_file)
        
        # 获取虚拟机快照
        snapshots = get_vm_snapshots(vm_file)
        
        # 获取虚拟机配置
        config = get_vm_config(vm_file)
        
        return jsonify({
            'success': True,
            'vm_info': {
                'name': vm_name,
                'path': vm_file,
                'status': vm_status,
                'snapshots': snapshots,
                'config': config
            }
        })
    except Exception as e:
        logger.error(f"获取{vm_type_name}虚拟机详细信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取{vm_type_name}虚拟机详细信息失败: {str(e)}'
        })

# 通用函数 - 发送脚本到虚拟机
def send_script_generic(vm_type_name):
    """向虚拟机发送脚本的通用函数"""
    logger.info(f"收到向{vm_type_name}虚拟机发送脚本请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        script_name = data.get('script_name')
        
        if not vm_name or not script_name:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称或脚本名称参数'
            })
        
        # 获取虚拟机IP
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            return jsonify({
                'success': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址'
            })
        
        # 检查脚本文件是否存在
        script_path = os.path.join(r'D:\macos_vm\macos_sh', script_name)
        if not os.path.exists(script_path):
            return jsonify({
                'success': False,
                'message': f'脚本文件 {script_name} 不存在'
            })
        
        # 检查虚拟机状态和SSH互信
        try:
            vm_info = get_vm_online_status(vm_name)
            
            if vm_info['status'] != 'online' or not vm_info.get('ssh_trust', False):
                return jsonify({
                    'success': False,
                    'message': f'虚拟机 {vm_name} 未在线或未建立SSH互信'
                })
            
            # 使用scp发送脚本
            import subprocess
            scp_cmd = [
                'scp',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'ConnectTimeout=10',
                script_path,
                f"{vm_username}@{vm_info['ip']}:{script_remote_path}{script_name}"
            ]
            
            logger.debug(f"执行SCP命令: {' '.join(scp_cmd)}")
            result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"脚本发送成功到虚拟机 {vm_name} ({vm_info['ip']})")
                return jsonify({
                    'success': True,
                    'message': f'脚本 {script_name} 发送成功到虚拟机 {vm_name}',
                    'file_path': f'{script_remote_path}{script_name}'
                })
            else:
                error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                logger.error(f"脚本发送失败到虚拟机 {vm_name}: {error_msg}")
                
                # 根据错误类型提供更详细的错误信息
                if 'Permission denied' in error_msg:
                    error_detail = 'SSH认证失败，请检查SSH互信设置'
                elif 'Connection refused' in error_msg:
                    error_detail = 'SSH连接被拒绝，请检查SSH服务是否运行'
                elif 'No route to host' in error_msg:
                    error_detail = '无法连接到主机，请检查网络连接'
                else:
                    error_detail = f'SCP传输失败: {error_msg}'
                
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
        logger.error(f"向{vm_type_name}虚拟机发送脚本失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'向{vm_type_name}虚拟机发送脚本失败: {str(e)}'
        })

# 通用函数 - 添加脚本执行权限
def add_permissions_generic(vm_type_name):
    """为虚拟机添加脚本执行权限的通用函数"""
    logger.info(f"收到为{vm_type_name}虚拟机添加脚本执行权限请求")
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
            'success': success,
            'message': message
        })
    except Exception as e:
        logger.error(f"为{vm_type_name}虚拟机添加脚本执行权限失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'为{vm_type_name}虚拟机添加脚本执行权限失败: {str(e)}'
        })

# 通用函数 - 获取IP状态
def get_ip_status_generic(vm_name, vm_type_name, vm_dir):
    """获取虚拟机IP状态的通用函数"""
    logger.info(f"收到获取{vm_type_name}虚拟机IP状态请求: {vm_name}")
    try:
        # 查找虚拟机文件
        vm_file = find_vm_file(vm_name)
        if not vm_file:
            return jsonify({
                'success': False,
                'message': f'虚拟机 {vm_name} 文件不存在'
            })
        
        # 检查是否在指定目录中
        if not vm_file.startswith(vm_dir):
            return jsonify({
                'success': False,
                'message': f'虚拟机 {vm_name} 不在{vm_type_name}目录中'
            })
        
        # 获取IP状态
        ip_status = get_vm_ip_status(vm_name)
        
        return jsonify({
            'success': True,
            'ip_status': ip_status
        })
    except Exception as e:
        logger.error(f"获取{vm_type_name}虚拟机IP状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取{vm_type_name}虚拟机IP状态失败: {str(e)}'
        })

# 确保 web/templates/ 目录下有 login.html 和 dashboard.html 文件，否则会报错。
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    logger.debug("登录页面访问")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        logger.debug(f"用户尝试登录: {username}")
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            logger.info(f"用户 {username} 登录成功")
            return redirect(url_for('clone_vm_page'))
        else:
            logger.warning(f"用户 {username} 登录失败")
            flash('用户名或密码错误')
    return render_template('login.html')
    
@app.route('/dashboard')
@login_required
def dashboard():
    logger.debug("访问dashboard页面")
    #获取虚拟机名称
    vm_temp_dir = r'D:\macos_vm\NewVM\10.12'
    vm_chengpin_dir = r'D:\macos_vm\NewVM\chengpin_vm'
    vms = []
    vm_data=[]
    
    logger.debug(f"扫描成品虚拟机目录: {vm_chengpin_dir}")
    for root, dirs, files in os.walk(vm_chengpin_dir):
        for fname in files:
            if fname.endswith('.vmx'):
                vms.append({
                    'name': fname,
                    'ip':'未获取到',
                    'status': '已关闭',
                    'imessage': '未知'
                    })
                logger.debug(f"找到成品虚拟机: {fname}")
    
    logger.debug(f"扫描临时虚拟机目录: {vm_temp_dir}")
    for root, dirs, files2 in os.walk(vm_temp_dir):
        for fname2 in files2:
            if fname2.endswith('.vmx'):
                vm_data.append({
                    'vm_name': fname2,
                    'vm_ip': '未获取到',
                    'vm_version': '未知',
                    'vm_status': '已经关闭',
                    'cl_status': '未执行',
                    'sh_status': '未执行'
                })
                logger.debug(f"找到临时虚拟机: {fname2}")

    #成品vm路径：D:\macos_vm\NewVM\10.12
    vm_list=vms
    #临时克隆vm路径：D:\macos_vm\NewVM\chengpin_vm
    vm_data=vm_data
    wuma_list = [
        {'name': 'macOS-10.12', 'available': 5, 'used': 2},
        {'name': 'macOS-10.15', 'available': 3, 'used': 1},
        {'name': 'macOS-11.0', 'available': 8, 'used': 4},
    ]
    
    # 读取 macos_sh 目录下脚本文件
    script_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'macos_sh')
    script_list = []
    logger.debug(f"扫描脚本目录: {script_dir}")
    if os.path.exists(script_dir):
        for fname in os.listdir(script_dir):
            fpath = os.path.join(script_dir, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y/%m/%d %H:%M')
                size = stat.st_size
                script_list.append({'name': fname, 'mtime': mtime, 'size': size})
                logger.debug(f"找到脚本文件: {fname}, 大小: {size} bytes")
    script_list.sort(key=lambda x: x['name'])
    
    logger.info(f"Dashboard数据准备完成 - 成品VM: {len(vm_list)}, 临时VM: {len(vm_data)}, 脚本: {len(script_list)}")
    return render_template('dashboard.html', username=session.get('username'), vm_list=vm_list,vm_data=vm_data, script_list=script_list, wuma_list=wuma_list)

@app.route('/clone_vm')
@login_required
def clone_vm_page():
    """克隆虚拟机页面"""
    # 获取模板虚拟机列表
    template_vms = []
  #  template_dir = r'D:\macos_vm\TemplateVM\macos10.12'
    if os.path.exists(template_dir):
        for root, dirs, files in os.walk(template_dir):
            for fname in files:
                if fname.endswith('.vmx'):
                    template_vms.append({'name': fname})
    
    # 获取五码配置文件列表（与五码管理一致）
    configs = []
    config_dir = wuma_config_dir
    
    # 确保config目录存在
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
        logger.info("创建config目录")
    
    # 查找config目录下的所有.txt文件
    if os.path.exists(config_dir):
        for filename in os.listdir(config_dir):
            if filename.endswith('.txt'):
                file_path = os.path.join(config_dir, filename)
                
                # 检查文件是否为合规的五码文本文件
                if is_valid_wuma_file(file_path):
                    config_name = filename[:-4]  # 去掉.txt后缀
                    # 计算可用五码数量
                    available_count = count_available_wuma(file_path)
                    configs.append({
                        'name': config_name,
                        'display_name': filename,
                        'path': file_path,
                        'available_count': available_count
                    })
                    logger.info(f"发现合规的五码文件: {filename}, 可用五码数量: {available_count}")
                else:
                    logger.warning(f"跳过不合规的文件: {filename}")
    
    # 按名称排序
    configs.sort(key=lambda x: x['name'])
    
    return render_template('clone_vm.html', 
                         template_vms=template_vms, 
                         configs=configs,
                         clone_dir=clone_dir)

@app.route('/vm_management')
@login_required
def vm_management_page():
    """虚拟机管理页面"""
    return render_template('vm_management.html')

@app.route('/vm_info')
@login_required
def vm_info_page():
    """虚拟机成品信息页面"""
    return render_template('vm_info.html')

@app.route('/api/vm_info_list')
@login_required
def api_vm_info_list():
    """获取虚拟机信息列表"""
    try:
        # 扫描虚拟机目录
        vm_dir = r'D:\macos_vm\NewVM'
        vms = []
        
        # 批量获取运行中的虚拟机列表（只执行一次vmrun命令）
        running_vms = set()
        try:
            vmrun_path = get_vmrun_path()
            
            list_cmd = [vmrun_path, 'list']
            result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                running_vms = set(result.stdout.strip().split('\n')[1:])
        except Exception as e:
            print(f"[DEBUG] 获取运行中虚拟机列表失败: {str(e)}")
        
        if os.path.exists(vm_dir):
            for root, dirs, files in os.walk(vm_dir):
                for file in files:
                    if file.endswith('.vmx'):
                        vm_path = os.path.join(root, file)
                        vm_name = os.path.splitext(file)[0]
                        
                        # 获取虚拟机状态
                        vm_status = 'stopped'
                        if vm_path in running_vms:
                            vm_status = 'running'
                        
                        # 获取创建时间（使用文件修改时间）
                        try:
                            create_time = datetime.datetime.fromtimestamp(os.path.getmtime(vm_path))
                            create_time_str = create_time.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            create_time_str = '未知'
                        
                        # 获取五码信息
                        wuma_info = get_wuma_info(vm_name)
                        has_wuma = wuma_info is not None
                        
                        # 获取配置信息
                        config_info = get_vm_config(vm_path)
                        
                        vms.append({
                            'name': vm_name,
                            'status': vm_status,
                            'create_time': create_time_str,
                            'config_info': config_info,
                            'has_wuma': has_wuma,
                            'wuma_info': wuma_info
                        })
        
        return jsonify({
            'success': True,
            'vms': vms
        })
        
    except Exception as e:
        print(f"[DEBUG] 获取虚拟机信息列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取虚拟机信息失败: {str(e)}'
        })

@app.route('/vm_script')
@login_required
def vm_script_page():
    """虚拟机脚本管理页面"""
    return render_template('vm_script.html')



@app.route('/wuma')
@login_required
def wuma_page():
    """虚拟机五码管理页面"""
    return render_template('wuma.html')

@app.route('/mupan')
@login_required
def mupan_page():
    """虚拟机母盘管理页面"""
    return render_template('mupan.html')

@app.route('/test_mupan')
def test_mupan_page():
    """母盘API测试页面"""
    return render_template('test_mupan_direct.html')

@app.route('/api/mupan_list')
@login_required
def api_mupan_list():
    """获取母盘虚拟机列表"""
    logger.info("收到母盘虚拟机列表请求")
    try:
        # 扫描TemplateVM目录
        template_vms = []
        
        logger.info(f"扫描目录: {template_dir}")
        if os.path.exists(template_dir):
            logger.info("TemplateVM目录存在")
            for root, dirs, files in os.walk(template_dir):
                logger.info(f"扫描子目录: {root}")
                for file in files:
                    if file.endswith('.vmx'):
                        vm_path = os.path.join(root, file)
                        vm_name = os.path.splitext(file)[0]  # 去掉.vmx后缀
                        logger.info(f"找到vmx文件: {vm_path}, 名称: {vm_name}")
                        
                        # 获取文件夹名称作为系统版本
                        folder_name = os.path.basename(root)
                        system_version = folder_name
                        logger.info(f"系统版本: {system_version}")
                        
                        # 获取同vmx文件名的vmdk文件大小
                        vmdk_path = os.path.join(root, f"{vm_name}.vmdk")
                        size_str = "未知"
                        if os.path.exists(vmdk_path):
                            try:
                                file_size = os.path.getsize(vmdk_path)
                                size_str = f"{file_size / (1024**3):.1f}GB"
                                logger.info(f"vmdk文件大小: {size_str}")
                            except:
                                size_str = "未知"
                                logger.warning(f"无法获取vmdk文件大小: {vmdk_path}")
                        else:
                            logger.warning(f"vmdk文件不存在: {vmdk_path}")
                        
                        # 获取vmx文件创建时间
                        try:
                            create_time = datetime.datetime.fromtimestamp(os.path.getmtime(vm_path))
                            create_time_str = create_time.strftime('%Y-%m-%d %H:%M:%S')
                            logger.info(f"创建时间: {create_time_str}")
                        except:
                            create_time_str = "未知"
                            logger.warning(f"无法获取创建时间: {vm_path}")
                        
                        # 调用vmrun获取虚拟机状态
                        vm_status = get_vm_status(vm_path)
                        logger.info(f"虚拟机状态: {vm_status}")
                        
                        vm_data = {
                            'name': vm_name,
                            'path': vm_path,
                            'system_version': system_version,
                            'size': size_str,
                            'create_time': create_time_str,
                            'status': vm_status
                        }
                        template_vms.append(vm_data)
                        logger.info(f"添加虚拟机数据: {vm_data}")
        
        # 按名称排序
        template_vms.sort(key=lambda x: x['name'])
        logger.info(f"总共找到 {len(template_vms)} 个虚拟机")
        
        response_data = {
            'success': True,
            'data': template_vms
        }
        logger.info(f"返回数据: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"获取母盘虚拟机列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取母盘虚拟机列表失败: {str(e)}'
        })

@app.route('/encrypt_code')
@login_required
def encrypt_code_page():
    """代码加密页面"""
    return render_template('encrypt_code.html')

@app.route('/encrypt_wuma')
@login_required
def encrypt_wuma_page():
    """五码加密页面"""
    return render_template('encrypt_wuma.html')

@app.route('/encrypt_id')
@login_required
def encrypt_id_page():
    """id加密页面"""
    return render_template('encrypt_id.html')

@app.route('/proxy_assign')
@login_required
def proxy_assign_page():
    """代理ip分配页面"""
    return render_template('proxy_assign.html')

@app.route('/soft_version')
@login_required
def soft_version_page():
    """版本查看页面"""
    return render_template('soft_version.html')

@app.route('/soft_env')
@login_required
def soft_env_page():
    """环境变量页面"""
    return render_template('soft_env.html')

@app.route('/api/clone_vm', methods=['POST'])
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
            'start_time': datetime.datetime.now(),
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

def clone_vm_worker(task_id):
    """克隆虚拟机工作线程"""
    task = clone_tasks[task_id]
    params = task['params']
    
    # 调试打印：任务参数
    print(f"[DEBUG] 任务ID: {task_id}")
    print(f"[DEBUG] 任务参数: {params}")
    
    try:
        # 添加开始日志
        add_task_log(task_id, 'info', f'开始克隆任务: 模板={params["templateVM"]}, 数量={params["cloneCount"]}')
        print(f"[DEBUG] 开始克隆任务: 模板={params['templateVM']}, 数量={params['cloneCount']}")
        
        # 验证模板虚拟机是否存在
        template_vm_name = params['templateVM']
        template_path = None
        
        # 在template_dir中查找匹配的.vmx文件
        if os.path.exists(template_dir):
            for root, dirs, files in os.walk(template_dir):
                for file in files:
                    if file == template_vm_name and file.endswith('.vmx'):
                        template_path = os.path.join(root, file)
                        break
                if template_path:
                    break
        
        print(f"[DEBUG] 模板虚拟机名称: {template_vm_name}")
        print(f"[DEBUG] 找到的模板路径: {template_path}")
        print(f"[DEBUG] 模板路径是否存在: {os.path.exists(template_path) if template_path else False}")
        
        if not template_path or not os.path.exists(template_path):
            add_task_log(task_id, 'error', f'模板虚拟机不存在: {template_vm_name}')
            print(f"[DEBUG] 错误：模板虚拟机不存在: {template_vm_name}")
            task['status'] = 'failed'
            return
        
        # 确保目标目录存在
        target_dir = clone_dir  # 使用全局配置中的克隆目录
        print(f"[DEBUG] 目标目录: {target_dir}")
        print(f"[DEBUG] 目标目录是否存在: {os.path.exists(target_dir)}")
        
        os.makedirs(target_dir, exist_ok=True)
        add_task_log(task_id, 'info', f'目标目录: {target_dir}')
        print(f"[DEBUG] 目标目录创建/确认完成")
        
        # 创建虚拟机快照（如果启用）
        create_snapshot = params.get('createSnapshot', 'true') == 'true'
        snapshot_name = None
        print(f"[DEBUG] 是否创建快照: {create_snapshot}")
        
        if create_snapshot:
            add_task_log(task_id, 'info', '开始创建虚拟机快照...')
            print(f"[DEBUG] 开始创建虚拟机快照...")
            
            vmrun_path = get_vmrun_path()
            
            print(f"[DEBUG] vmrun路径: {vmrun_path}")
            print(f"[DEBUG] vmrun是否存在: {os.path.exists(vmrun_path)}")
            
            # 生成快照名称
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            vm_name_without_ext = params['templateVM'].replace('.vmx', '')
            
            print(f"[DEBUG] 时间戳: {timestamp}")
            print(f"[DEBUG] 虚拟机名称(无扩展名): {vm_name_without_ext}")
            
            # 使用用户自定义的快照命名模式
            snapshot_pattern = params.get('snapshotName', '{vmname}_snapshot_{timestamp}')
            if snapshot_pattern == 'custom':
                snapshot_pattern = params.get('customSnapshotName', '{vmname}_snapshot_{timestamp}')
            snapshot_name = snapshot_pattern.replace('{vmname}', vm_name_without_ext).replace('{timestamp}', timestamp)
            
            print(f"[DEBUG] 快照命名模式: {snapshot_pattern}")
            print(f"[DEBUG] 生成的快照名称: {snapshot_name}")
            
            snapshot_cmd = [
                vmrun_path,
                '-T', 'ws',
                'snapshot',
                template_path,
                snapshot_name
            ]
            
            print(f"[DEBUG] 快照命令: {' '.join(snapshot_cmd)}")
            # 只在后台打印命令详情，不发送到前端
            print(f"[DEBUG] 执行快照命令: {' '.join(snapshot_cmd)}")
            
            try:
                # 执行快照命令
                print(f"[DEBUG] 开始执行快照命令...")
                
                # 记录详细的快照命令执行信息
                add_task_log(task_id, 'info', f'执行快照命令: vmrun snapshot {template_path} {snapshot_name}')
                
                # 记录命令开始时间
                start_time = datetime.datetime.now()
                print(f"[DEBUG] 快照命令开始时间: {start_time}")
                
                result = subprocess.run(snapshot_cmd, capture_output=True, text=True, timeout=120)
                
                # 记录命令结束时间
                end_time = datetime.datetime.now()
                duration = (end_time - start_time).total_seconds()
                print(f"[DEBUG] 快照命令结束时间: {end_time}")
                print(f"[DEBUG] 快照命令执行时长: {duration} 秒")
                
                print(f"[DEBUG] 快照命令返回码: {result.returncode}")
                print(f"[DEBUG] 快照命令输出: {result.stdout}")
                if result.stderr:
                    print(f"[DEBUG] 快照命令错误: {result.stderr}")
                
                # 记录详细的快照执行结果
                add_task_log(task_id, 'info', f'快照命令执行完成，返回码: {result.returncode}, 耗时: {duration:.2f}秒')
                if result.stdout:
                    add_task_log(task_id, 'info', f'快照命令输出: {result.stdout.strip()}')
                if result.stderr:
                    add_task_log(task_id, 'warning', f'快照命令错误: {result.stderr.strip()}')
                
                if result.returncode == 0:
                    add_task_log(task_id, 'success', f'虚拟机快照创建成功: {snapshot_name}')
                    print(f"[DEBUG] 快照创建成功: {snapshot_name}")
                else:
                    add_task_log(task_id, 'error', f'虚拟机快照创建失败: {result.stderr}')
                    print(f"[DEBUG] 快照创建失败: {result.stderr}")
                    task['status'] = 'failed'
                    return
            except subprocess.TimeoutExpired:
                add_task_log(task_id, 'error', '虚拟机快照创建超时')
                print(f"[DEBUG] 快照创建超时")
                task['status'] = 'failed'
                return
            except Exception as e:
                add_task_log(task_id, 'error', f'虚拟机快照创建时发生错误: {str(e)}')
                print(f"[DEBUG] 快照创建异常: {str(e)}")
                task['status'] = 'failed'
                return
        else:
            add_task_log(task_id, 'info', '跳过快照创建，直接开始克隆任务')
            print(f"[DEBUG] 跳过快照创建，直接开始克隆任务")
        
        # 获取五码配置文件
        config_file = params.get('configPlist')
        wuma_codes = []
        print(f"[DEBUG] 五码配置文件: {config_file}")
        print(f"[DEBUG] 配置文件是否存在: {os.path.exists(config_file)}")
        
        if os.path.exists(config_file):
            # 读取五码配置文件中的有效五码
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                if content:
                    lines = content.split('\n')
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # 检查格式：:ROM:MLB:SN:BoardID:Model:
                        if not (line.startswith(':') and line.endswith(':')):
                            continue
                        
                        # 分割并检查字段数量
                        parts = line.split(':')
                        if len(parts) != 7:  # 包括首尾的空字符串
                            continue
                        
                        # 检查中间5个字段是否不为空
                        if any(not parts[i].strip() for i in range(1, 6)):
                            continue
                        
                        wuma_codes.append(line)
                
                print(f"[DEBUG] 读取到有效五码数量: {len(wuma_codes)}")
            except Exception as e:
                print(f"[DEBUG] 读取五码配置文件失败: {str(e)}")
                add_task_log(task_id, 'error', f'读取五码配置文件失败: {str(e)}')
                task['status'] = 'failed'
                return
        else:
            print(f"[DEBUG] 五码配置文件不存在: {config_file}")
            add_task_log(task_id, 'error', f'五码配置文件不存在: {config_file}')
            task['status'] = 'failed'
            return
        
        print(f"[DEBUG] 找到有效五码数量: {len(wuma_codes)}")
        print(f"[DEBUG] 五码列表: {wuma_codes[:3]}...")  # 只显示前3个
        
        # 开始克隆
        clone_count = int(params['cloneCount'])
        print(f"[DEBUG] 开始克隆，总数: {clone_count}")
        
        add_task_log(task_id, 'info', f'找到 {len(wuma_codes)} 个有效五码，需要克隆 {clone_count} 个虚拟机')
        
        # 发送初始进度信息
        initial_progress = {
            'type': 'progress',
            'current': 0,
            'total': clone_count,
            'current_vm': '',
            'current_vm_progress': 0,
            'estimated_remaining': clone_count * 30  # 预估总时间
        }
        task['logs'].append(initial_progress)
        
        for i in range(clone_count):
            try:
                print(f"[DEBUG] 开始克隆第 {i+1}/{clone_count} 个虚拟机")
                
                # 生成虚拟机名称和文件夹名称
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                vm_name_pattern = params['namingPattern']
                if vm_name_pattern == 'custom':
                    vm_name_pattern = params.get('customNamingPattern', 'VM_{timestamp}_{index}')
                
                print(f"[DEBUG] 虚拟机命名模式: {vm_name_pattern}")
                
                # 生成虚拟机名称（不包含.vmx扩展名）
                vm_name_without_ext_generated = vm_name_pattern.replace('{timestamp}', timestamp).replace('{index}', str(i+1)).replace('{vmname}', vm_name_without_ext)
                
                # 创建虚拟机文件夹名称
                vm_folder_name = vm_name_without_ext_generated
                vm_folder_path = os.path.join(target_dir, vm_folder_name)
                
                # 确保虚拟机文件夹存在
                os.makedirs(vm_folder_path, exist_ok=True)
                print(f"[DEBUG] 创建虚拟机文件夹: {vm_folder_path}")
                
                # 生成完整的虚拟机文件路径
                vm_name = vm_name_without_ext_generated + '.vmx'
                vm_file_path = os.path.join(vm_folder_path, vm_name)
                
                print(f"[DEBUG] 生成的虚拟机文件夹: {vm_folder_name}")
                print(f"[DEBUG] 生成的虚拟机文件路径: {vm_file_path}")
                
                # 分配五码
                wuma_code = wuma_codes[i % len(wuma_codes)] if wuma_codes else None
                print(f"[DEBUG] 分配的五码: {wuma_code}")
                
                add_task_log(task_id, 'info', f'开始克隆第 {i+1}/{clone_count} 个虚拟机: {vm_name}')
                add_task_log(task_id, 'info', f'虚拟机文件夹: {vm_folder_path}')
                if wuma_code:
                    add_task_log(task_id, 'info', f'使用五码: {wuma_code[:50]}...')  # 只显示前50个字符
                
                # 发送当前虚拟机进度信息
                current_vm_progress = {
                    'type': 'progress',
                    'current': i,
                    'total': clone_count,
                    'current_vm': vm_name,
                    'current_vm_progress': 0,  # 开始克隆
                    'estimated_remaining': max(0, (clone_count - i) * 30)
                }
                task['logs'].append(current_vm_progress)
                
                # 执行克隆命令
                vmrun_path = get_vmrun_path()
                
                print(f"[DEBUG] 克隆使用的vmrun路径: {vmrun_path}")
                
                # 构建克隆命令
                if create_snapshot and snapshot_name:
                    # 从快照克隆
                    clone_cmd = [
                        vmrun_path,
                        'clone',
                        template_path,
                        vm_file_path,
                        'linked',
                        '-snapshot',
                        snapshot_name
                    ]
                    add_task_log(task_id, 'info', f'从快照克隆: {snapshot_name}')
                    print(f"[DEBUG] 从快照克隆: {snapshot_name}")
                else:
                    # 直接从模板克隆
                    clone_cmd = [
                        vmrun_path,
                        'clone',
                        template_path,
                        vm_file_path,
                        'linked'
                    ]
                    add_task_log(task_id, 'info', f'直接从模板克隆')
                    print(f"[DEBUG] 直接从模板克隆")
                
                print(f"[DEBUG] 克隆命令: {' '.join(clone_cmd)}")
                # 只在后台打印命令详情，不发送到前端
                print(f"[DEBUG] 执行命令: {' '.join(clone_cmd)}")
                
                # 记录详细的命令执行信息
                add_task_log(task_id, 'info', f'执行克隆命令: vmrun clone {template_path} {vm_file_path}')
                print(f"[DEBUG] 开始执行克隆命令...")
                
                # 记录命令开始时间
                start_time = datetime.datetime.now()
                print(f"[DEBUG] 命令开始时间: {start_time}")
                
                result = subprocess.run(clone_cmd, capture_output=True, text=True, timeout=300)
                
                # 记录命令结束时间
                end_time = datetime.datetime.now()
                duration = (end_time - start_time).total_seconds()
                print(f"[DEBUG] 命令结束时间: {end_time}")
                print(f"[DEBUG] 命令执行时长: {duration} 秒")
                
                print(f"[DEBUG] 克隆命令返回码: {result.returncode}")
                print(f"[DEBUG] 克隆命令输出: {result.stdout}")
                if result.stderr:
                    print(f"[DEBUG] 克隆命令错误: {result.stderr}")
                
                # 记录详细的执行结果
                add_task_log(task_id, 'info', f'克隆命令执行完成，返回码: {result.returncode}, 耗时: {duration:.2f}秒')
                if result.stdout:
                    add_task_log(task_id, 'info', f'命令输出: {result.stdout.strip()}')
                if result.stderr:
                    add_task_log(task_id, 'warning', f'命令错误: {result.stderr.strip()}')
                
                if result.returncode == 0:
                    add_task_log(task_id, 'success', f'虚拟机 {vm_name} 克隆成功')
                    print(f"[DEBUG] 虚拟机 {vm_name} 克隆成功")
                    task['stats']['success'] += 1
                    
                    # 更新vmx文件中的displayName
                    vm_display_name = vm_name_without_ext_generated  # 使用虚拟机文件夹名称作为显示名称
                    if update_vmx_display_name(vm_file_path, vm_display_name):
                        add_task_log(task_id, 'info', f'虚拟机 {vm_name} 的displayName已更新为: {vm_display_name}')
                        print(f"[DEBUG] displayName更新成功: {vm_display_name}")
                    else:
                        add_task_log(task_id, 'warning', f'虚拟机 {vm_name} 的displayName更新失败')
                        print(f"[DEBUG] displayName更新失败")
                    
                    # 如果配置了自动启动
                    if params.get('autoStart') == 'true':
                        start_cmd = [vmrun_path, 'start', vm_file_path, 'nogui']
                        print(f"[DEBUG] 自动启动命令: {' '.join(start_cmd)}")
                        add_task_log(task_id, 'info', f'执行启动命令: vmrun start {vm_file_path}')
                        
                        # 记录启动命令开始时间
                        start_time = datetime.datetime.now()
                        print(f"[DEBUG] 启动命令开始时间: {start_time}")
                        
                        result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=60)
                        
                        # 记录启动命令结束时间
                        end_time = datetime.datetime.now()
                        duration = (end_time - start_time).total_seconds()
                        print(f"[DEBUG] 启动命令结束时间: {end_time}")
                        print(f"[DEBUG] 启动命令执行时长: {duration} 秒")
                        print(f"[DEBUG] 启动命令返回码: {result.returncode}")
                        print(f"[DEBUG] 启动命令输出: {result.stdout}")
                        if result.stderr:
                            print(f"[DEBUG] 启动命令错误: {result.stderr}")
                        
                        # 记录详细的启动执行结果
                        add_task_log(task_id, 'info', f'启动命令执行完成，返回码: {result.returncode}, 耗时: {duration:.2f}秒')
                        if result.stdout:
                            add_task_log(task_id, 'info', f'启动命令输出: {result.stdout.strip()}')
                        if result.stderr:
                            add_task_log(task_id, 'warning', f'启动命令错误: {result.stderr.strip()}')
                        
                        if result.returncode == 0:
                            add_task_log(task_id, 'success', f'虚拟机 {vm_name} 启动成功')
                        else:
                            add_task_log(task_id, 'error', f'虚拟机 {vm_name} 启动失败: {result.stderr}')
                else:
                    add_task_log(task_id, 'error', f'虚拟机 {vm_name} 克隆失败: {result.stderr}')
                    print(f"[DEBUG] 虚拟机 {vm_name} 克隆失败: {result.stderr}")
                    task['stats']['error'] += 1
                
                # 更新进度
                task['progress']['current'] = i + 1
                print(f"[DEBUG] 更新进度: {i+1}/{clone_count}")
                
                # 发送详细进度信息
                progress_data = {
                    'type': 'progress',
                    'current': i + 1,
                    'total': clone_count,
                    'current_vm': vm_name,
                    'current_vm_progress': 100,  # 单个虚拟机克隆完成
                    'estimated_remaining': max(0, (clone_count - i - 1) * 30)  # 预估剩余时间（秒）
                }
                task['logs'].append(progress_data)
                
                time.sleep(1)  # 避免过快执行
                
            except subprocess.TimeoutExpired:
                add_task_log(task_id, 'error', f'克隆第 {i+1} 个虚拟机超时')
                print(f"[DEBUG] 克隆第 {i+1} 个虚拟机超时")
                task['stats']['error'] += 1
            except Exception as e:
                add_task_log(task_id, 'error', f'克隆第 {i+1} 个虚拟机时发生错误: {str(e)}')
                print(f"[DEBUG] 克隆第 {i+1} 个虚拟机时发生错误: {str(e)}")
                task['stats']['error'] += 1
        
        # 任务完成
        print(f"[DEBUG] 任务完成统计 - 成功: {task['stats']['success']}, 失败: {task['stats']['error']}")
        
        if task['stats']['error'] == 0:
            task['status'] = 'completed'
            add_task_log(task_id, 'success', f'所有虚拟机克隆完成！成功: {task["stats"]["success"]}')
            print(f"[DEBUG] 所有虚拟机克隆完成！成功: {task['stats']['success']}")
        else:
            task['status'] = 'completed_with_errors'
            add_task_log(task_id, 'warning', f'克隆任务完成，但有错误。成功: {task["stats"]["success"]}, 失败: {task["stats"]["error"]}')
            print(f"[DEBUG] 克隆任务完成，但有错误。成功: {task['stats']['success']}, 失败: {task['stats']['error']}")
        
    except Exception as e:
        add_task_log(task_id, 'error', f'克隆任务发生严重错误: {str(e)}')
        print(f"[DEBUG] 克隆任务发生严重错误: {str(e)}")
        task['status'] = 'failed'

def update_vmx_display_name(vmx_file_path, new_display_name):
    """更新vmx文件中的displayName参数"""
    try:
        print(f"[DEBUG] 开始更新vmx文件: {vmx_file_path}")
        print(f"[DEBUG] 新的displayName: {new_display_name}")
        
        # 检查文件是否存在
        if not os.path.exists(vmx_file_path):
            print(f"[DEBUG] vmx文件不存在: {vmx_file_path}")
            return False
        
        # 读取vmx文件
        with open(vmx_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"[DEBUG] 读取到 {len(lines)} 行内容")
        
        # 查找并替换displayName参数
        updated = False
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped.startswith('displayName'):
                old_line = line_stripped
                new_line = f'displayName = "{new_display_name}"\n'
                lines[i] = new_line
                updated = True
                print(f"[DEBUG] 找到displayName行: {old_line}")
                print(f"[DEBUG] 更新为: {new_line.strip()}")
                break
        
        if not updated:
            # 如果没有找到displayName行，在文件末尾添加
            new_line = f'displayName = "{new_display_name}"\n'
            lines.append(new_line)
            print(f"[DEBUG] 未找到displayName行，在文件末尾添加: {new_line.strip()}")
        
        # 写回文件
        with open(vmx_file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print(f"[DEBUG] vmx文件更新成功")
        
        # 验证更新结果
        with open(vmx_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if f'displayName = "{new_display_name}"' in content:
                print(f"[DEBUG] 验证成功：displayName已正确更新")
                return True
            else:
                print(f"[DEBUG] 验证失败：displayName未找到")
                return False
        
    except Exception as e:
        print(f"[DEBUG] 更新vmx文件失败: {str(e)}")
        return False

def add_task_log(task_id, level, message):
    """添加任务日志"""
    if task_id in clone_tasks:
        task = clone_tasks[task_id]
        log_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'level': level,
            'message': message
        }
        task['logs'].append(log_entry)
        
        # 同时写入日志文件
        log_file_path = f'logs/task_{task_id}.log'
        os.makedirs('logs', exist_ok=True)
        try:
            with open(log_file_path, 'a', encoding='utf-8') as f:
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f'[{timestamp}] [{level.upper()}] {message}\n')
        except Exception as e:
            print(f"[DEBUG] 写入日志文件失败: {str(e)}")

@app.route('/api/clone_logs/<task_id>')
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
            
            while task['status'] in ['running'] and timeout_counter < max_timeout:
                # 发送新日志和进度数据
                while last_log_index < len(task['logs']):
                    log_entry = task['logs'][last_log_index]
                    
                    # 检查是否是进度数据
                    if isinstance(log_entry, dict) and log_entry.get('type') == 'progress':
                        # 发送进度数据
                        try:
                            yield f"data: {json.dumps(log_entry, ensure_ascii=False)}\n\n"
                        except Exception as e:
                            print(f"[DEBUG] 进度数据序列化失败: {str(e)}")
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
                            print(f"[DEBUG] 日志数据序列化失败: {str(e)}")
                            yield f"data: {json.dumps({'type': 'error', 'message': '日志数据序列化失败'})}\n\n"
                    
                    last_log_index += 1
                
                # 发送统计更新
                try:
                    stats_data = {
                        'type': 'stats',
                        'stats': task['stats']
                    }
                    yield f"data: {json.dumps(stats_data, ensure_ascii=False)}\n\n"
                except Exception as e:
                    print(f"[DEBUG] 统计数据序列化失败: {str(e)}")
                    yield f"data: {json.dumps({'type': 'error', 'message': '统计数据序列化失败'})}\n\n"
                
                timeout_counter += 1
                time.sleep(1)
            
            # 发送完成信号
            try:
                complete_data = {
                    'type': 'complete',
                    'success': task['status'] == 'completed',
                    'stats': task['stats']
                }
                yield f"data: {json.dumps(complete_data, ensure_ascii=False)}\n\n"
            except Exception as e:
                print(f"[DEBUG] 完成信号序列化失败: {str(e)}")
                yield f"data: {json.dumps({'type': 'error', 'message': '完成信号序列化失败'})}\n\n"
            
        except Exception as e:
            print(f"[DEBUG] 日志流生成错误: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'日志流错误: {str(e)}'})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/task_logs/<task_id>')
@login_required
def api_get_task_logs(task_id):
    """获取任务日志文件内容"""
    try:
        log_file_path = f'logs/task_{task_id}.log'
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

@app.route('/api/vm_list')
@login_required
def api_vm_list():
    """获取虚拟机列表"""
    logger.info("收到获取虚拟机列表API请求")
    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        logger.debug(f"分页参数 - 页码: {page}, 每页大小: {page_size}")
        
        # 扫描虚拟机目录
        vm_dir = r'D:\macos_vm\NewVM'
        vms = []
        stats = {'total': 0, 'running': 0, 'stopped': 0, 'online': 0}
        
        logger.debug(f"开始扫描虚拟机目录: {vm_dir}")
        
        # 批量获取运行中的虚拟机列表（只执行一次vmrun命令）
        running_vms = set()
        try:
            vmrun_path = get_vmrun_path()
            
            list_cmd = [vmrun_path, 'list']
            logger.debug(f"执行vmrun命令: {list_cmd}")
            result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                running_vms = set(result.stdout.strip().split('\n')[1:])  # 跳过标题行
                logger.debug(f"获取到运行中虚拟机: {len(running_vms)} 个")
            else:
                logger.warning(f"vmrun命令执行失败: {result.stderr}")
        except Exception as e:
            logger.error(f"获取运行中虚拟机列表失败: {str(e)}")
        
        if os.path.exists(vm_dir):
            for root, dirs, files in os.walk(vm_dir):
                for file in files:
                    if file.endswith('.vmx'):
                        vm_path = os.path.join(root, file)
                        vm_name = os.path.splitext(file)[0]
                        
                        # 快速判断虚拟机状态（基于文件名匹配）
                        vm_status = 'stopped'
                        for running_vm in running_vms:
                            if vm_name in running_vm:
                                vm_status = 'running'
                                break
                        
                        logger.debug(f"找到虚拟机: {vm_name}, 状态: {vm_status}")
                        
                        # 构建虚拟机基本信息
                        vm_info = {
                            'name': vm_name,
                            'path': vm_path,
                            'status': vm_status,
                            'online_status': 'unknown',  # 初始状态为未知
                            'online_reason': '',
                            'ip': '获取中...' if vm_status == 'running' else '-',
                            'ssh_trust': False,
                            'wuma_info': get_wuma_info(vm_name) or '未配置',
                            'ju_info': '未获取到ju值信息',  # JU值信息初始状态
                            'wuma_view_status': '未获取',  # 五码查看状态初始状态
                            'ssh_status': 'unknown'
                        }
                        vms.append(vm_info)
                        
                        # 更新统计信息
                        stats['total'] += 1
                        if vm_status == 'running':
                            stats['running'] += 1
                        elif vm_status == 'stopped':
                            stats['stopped'] += 1
        else:
            logger.warning(f"虚拟机目录不存在: {vm_dir}")
        
        # 对虚拟机进行排序：运行中的虚拟机排在前面
        vms.sort(key=lambda vm: (vm['status'] != 'running', vm['name']))
        
        # 计算分页
        total_count = len(vms)
        total_pages = (total_count + page_size - 1) // page_size
        start_index = (page - 1) * page_size
        end_index = min(start_index + page_size, total_count)
        
        # 分页数据
        paged_vms = vms[start_index:end_index] if vms else []
        
        logger.info(f"虚拟机列表获取完成 - 总数: {total_count}, 运行中: {stats['running']}, 已停止: {stats['stopped']}")
        
        return jsonify({
            'success': True,
            'vms': paged_vms,
            'stats': stats,
            'pagination': {
                'current_page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': total_pages,
                'start_index': start_index,
                'end_index': end_index
            }
        })
        
    except Exception as e:
        logger.error(f"获取虚拟机列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取虚拟机列表失败: {str(e)}'
        })

@app.route('/api/vm_details/<vm_name>')
@login_required
def api_vm_details(vm_name):
    """获取单个虚拟机的详细信息"""
    logger.debug(f"获取虚拟机 {vm_name} 的详细信息")
    try:
        # 获取虚拟机在线状态（包括IP和SSH互信）
        online_status = get_vm_online_status(vm_name)
        
        # 获取五码信息
        wuma_info = get_wuma_info(vm_name)
        
        return jsonify({
            'success': True,
            'vm_name': vm_name,
            'ip': online_status['ip'],
            'wuma_info': wuma_info,
            'online_status': online_status['status'],
            'online_reason': online_status['reason'],
            'ssh_trust': online_status['ssh_trust'],
            'ssh_port_open': online_status.get('ssh_port_open', False)
        })
        
    except Exception as e:
        logger.error(f"获取虚拟机 {vm_name} 详细信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取虚拟机详细信息失败: {str(e)}'
        })

@app.route('/api/vm_ip_status/<vm_name>')
@login_required
def api_vm_ip_status(vm_name):
    """获取虚拟机IP状态信息"""
    try:
        ip_status = get_vm_ip_status(vm_name)
        
        return jsonify({
            'success': True,
            'vm_name': vm_name,
            'ip_status': ip_status
        })
        
    except Exception as e:
        print(f"[DEBUG] 获取虚拟机IP状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取虚拟机IP状态失败: {str(e)}'
        })

@app.route('/api/vm_online_status', methods=['POST'])
@login_required
def api_vm_online_status():
    """异步获取虚拟机在线状态（只处理运行中的虚拟机）"""
    logger.info("收到异步获取虚拟机在线状态请求")
    try:
        data = request.get_json()
        vm_names = data.get('vm_names', [])
        
        if not vm_names:
            logger.warning("缺少虚拟机名称")
            return jsonify({'success': False, 'message': '缺少虚拟机名称'})
        
        logger.debug(f"开始异步获取 {len(vm_names)} 个虚拟机的在线状态")
        
        results = {}
        for vm_name in vm_names:
            try:
                logger.debug(f"获取虚拟机 {vm_name} 的在线状态")
                online_status = get_vm_online_status(vm_name)
                results[vm_name] = {
                    'online_status': online_status['status'],
                    'online_reason': online_status['reason'],
                    'ip': online_status['ip'],
                    'ssh_trust': online_status['ssh_trust'],
                    'ssh_port_open': online_status.get('ssh_port_open', False)
                }
                logger.debug(f"虚拟机 {vm_name} 在线状态: {online_status['status']}")
            except Exception as e:
                logger.error(f"获取虚拟机 {vm_name} 在线状态失败: {str(e)}")
                results[vm_name] = {
                    'online_status': 'error',
                    'online_reason': f'获取状态失败: {str(e)}',
                    'ip': None,
                    'ssh_trust': False
                }
        
        logger.info(f"异步获取完成，共处理 {len(results)} 个虚拟机")
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"异步获取虚拟机在线状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'异步获取失败: {str(e)}'
        })

@app.route('/api/vm_ip_monitor', methods=['POST'])
@login_required
def api_vm_ip_monitor():
    """批量监控虚拟机IP状态"""
    try:
        data = request.get_json()
        vm_names = data.get('vm_names', [])
        
        if not vm_names:
            return jsonify({'success': False, 'message': '缺少虚拟机名称'})
        
        results = {}
        for vm_name in vm_names:
            try:
                ip_status = get_vm_ip_status(vm_name)
                results[vm_name] = ip_status
            except Exception as e:
                results[vm_name] = {
                    'ip': None,
                    'status': 'error',
                    'message': f'监控失败: {str(e)}'
                }
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        print(f"[DEBUG] 批量监控IP状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量监控失败: {str(e)}'
        })

@app.route('/api/vm_start', methods=['POST'])
@login_required
def api_vm_start():
    """启动虚拟机"""
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        
        if not vm_name:
            return jsonify({'success': False, 'message': '缺少虚拟机名称'})
        
        # 查找虚拟机文件
        vm_file = find_vm_file(vm_name)
        if not vm_file:
            return jsonify({'success': False, 'message': f'找不到虚拟机: {vm_name}'})
        
        # 启动虚拟机
        vmrun_path = get_vmrun_path()
        
        print(f"[DEBUG] 启动虚拟机 {vm_name}")
        print(f"[DEBUG] 虚拟机文件路径: {vm_file}")
        print(f"[DEBUG] vmrun路径: {vmrun_path}")
        
        start_cmd = [vmrun_path, 'start', vm_file, 'nogui']
        print(f"[DEBUG] 启动命令: {' '.join(start_cmd)}")
        
        # 记录命令开始时间
        start_time = datetime.datetime.now()
        print(f"[DEBUG] 启动命令开始时间: {start_time}")
        
        result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=60)
        
        # 记录命令结束时间
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"[DEBUG] 启动命令结束时间: {end_time}")
        print(f"[DEBUG] 启动命令执行时长: {duration} 秒")
        print(f"[DEBUG] 启动命令返回码: {result.returncode}")
        print(f"[DEBUG] 启动命令输出: {result.stdout}")
        if result.stderr:
            print(f"[DEBUG] 启动命令错误: {result.stderr}")
        
        if result.returncode == 0:
            print(f"[DEBUG] 虚拟机 {vm_name} 启动成功")
            return jsonify({'success': True, 'message': '虚拟机启动成功'})
        else:
            print(f"[DEBUG] 虚拟机 {vm_name} 启动失败: {result.stderr}")
            return jsonify({'success': False, 'message': f'启动失败: {result.stderr}'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'启动失败: {str(e)}'})

@app.route('/api/vm_stop', methods=['POST'])
@login_required
def api_vm_stop():
    """停止虚拟机"""
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        
        if not vm_name:
            return jsonify({'success': False, 'message': '缺少虚拟机名称'})
        
        # 查找虚拟机文件
        vm_file = find_vm_file(vm_name)
        if not vm_file:
            return jsonify({'success': False, 'message': f'找不到虚拟机: {vm_name}'})
        
        # 停止虚拟机
        vmrun_path = get_vmrun_path()
        
        print(f"[DEBUG] 停止虚拟机 {vm_name}")
        print(f"[DEBUG] 虚拟机文件路径: {vm_file}")
        print(f"[DEBUG] vmrun路径: {vmrun_path}")
        
        stop_cmd = [vmrun_path, 'stop', vm_file, 'hard']
        print(f"[DEBUG] 停止命令: {' '.join(stop_cmd)}")
        
        # 记录命令开始时间
        start_time = datetime.datetime.now()
        print(f"[DEBUG] 停止命令开始时间: {start_time}")
        
        result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=60)
        
        # 记录命令结束时间
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"[DEBUG] 停止命令结束时间: {end_time}")
        print(f"[DEBUG] 停止命令执行时长: {duration} 秒")
        print(f"[DEBUG] 停止命令返回码: {result.returncode}")
        print(f"[DEBUG] 停止命令输出: {result.stdout}")
        if result.stderr:
            print(f"[DEBUG] 停止命令错误: {result.stderr}")
        
        if result.returncode == 0:
            print(f"[DEBUG] 虚拟机 {vm_name} 停止成功")
            return jsonify({'success': True, 'message': '虚拟机停止成功'})
        else:
            print(f"[DEBUG] 虚拟机 {vm_name} 停止失败: {result.stderr}")
            return jsonify({'success': False, 'message': f'停止失败: {result.stderr}'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'停止失败: {str(e)}'})

@app.route('/api/vm_restart', methods=['POST'])
@login_required
def api_vm_restart():
    """重启虚拟机"""
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        
        if not vm_name:
            return jsonify({'success': False, 'message': '缺少虚拟机名称'})
        
        # 查找虚拟机文件
        vm_file = find_vm_file(vm_name)
        if not vm_file:
            return jsonify({'success': False, 'message': f'找不到虚拟机: {vm_name}'})
        
        # 重启虚拟机
        vmrun_path = get_vmrun_path()
        
        print(f"[DEBUG] 重启虚拟机 {vm_name}")
        print(f"[DEBUG] 虚拟机文件路径: {vm_file}")
        print(f"[DEBUG] vmrun路径: {vmrun_path}")
        
        # 先停止虚拟机
        stop_cmd = [vmrun_path, 'stop', vm_file, 'hard']
        print(f"[DEBUG] 重启-停止命令: {' '.join(stop_cmd)}")
        
        # 记录停止命令开始时间
        stop_start_time = datetime.datetime.now()
        print(f"[DEBUG] 重启-停止命令开始时间: {stop_start_time}")
        
        stop_result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=60)
        
        # 记录停止命令结束时间
        stop_end_time = datetime.datetime.now()
        stop_duration = (stop_end_time - stop_start_time).total_seconds()
        print(f"[DEBUG] 重启-停止命令结束时间: {stop_end_time}")
        print(f"[DEBUG] 重启-停止命令执行时长: {stop_duration} 秒")
        print(f"[DEBUG] 重启-停止命令返回码: {stop_result.returncode}")
        print(f"[DEBUG] 重启-停止命令输出: {stop_result.stdout}")
        if stop_result.stderr:
            print(f"[DEBUG] 重启-停止命令错误: {stop_result.stderr}")
        
        # 等待一下再启动
        import time
        print(f"[DEBUG] 等待2秒后启动...")
        time.sleep(2)
        
        # 启动虚拟机
        start_cmd = [vmrun_path, 'start', vm_file, 'nogui']
        print(f"[DEBUG] 重启-启动命令: {' '.join(start_cmd)}")
        
        # 记录启动命令开始时间
        start_start_time = datetime.datetime.now()
        print(f"[DEBUG] 重启-启动命令开始时间: {start_start_time}")
        
        start_result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=60)
        
        # 记录启动命令结束时间
        start_end_time = datetime.datetime.now()
        start_duration = (start_end_time - start_start_time).total_seconds()
        print(f"[DEBUG] 重启-启动命令结束时间: {start_end_time}")
        print(f"[DEBUG] 重启-启动命令执行时长: {start_duration} 秒")
        print(f"[DEBUG] 重启-启动命令返回码: {start_result.returncode}")
        print(f"[DEBUG] 重启-启动命令输出: {start_result.stdout}")
        if start_result.stderr:
            print(f"[DEBUG] 重启-启动命令错误: {start_result.stderr}")
        
        if start_result.returncode == 0:
            print(f"[DEBUG] 虚拟机 {vm_name} 重启成功")
            return jsonify({'success': True, 'message': '虚拟机重启成功'})
        else:
            print(f"[DEBUG] 虚拟机 {vm_name} 重启失败: {start_result.stderr}")
            return jsonify({'success': False, 'message': f'重启失败: {start_result.stderr}'})
            
    except Exception as e:
        print(f"[DEBUG] 重启虚拟机失败: {str(e)}")
        return jsonify({'success': False, 'message': f'重启失败: {str(e)}'})

@app.route('/api/vm_info/<vm_name>')
@login_required
def api_vm_info(vm_name):
    """获取虚拟机详细信息"""
    try:
        vm_file = find_vm_file(vm_name)
        if not vm_file:
            return jsonify({'success': False, 'message': f'找不到虚拟机: {vm_name}'})
        
        # 获取详细信息
        vm_info = {
            'name': vm_name,
            'path': vm_file,
            'status': get_vm_status(vm_file),
            'ip': get_vm_ip(vm_name),
            'wuma_info': get_wuma_info(vm_name),
            'ssh_status': check_ssh_status(get_vm_ip(vm_name)) if get_vm_ip(vm_name) else 'offline',
            'snapshots': get_vm_snapshots(vm_file),
            'config': get_vm_config(vm_file)
        }
        
        return jsonify({
            'success': True,
            'vm_info': vm_info
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取信息失败: {str(e)}'})

@app.route('/api/vm_delete', methods=['POST'])
@login_required
def api_vm_delete():
    """删除虚拟机"""
    try:
        data = request.get_json()
        vm_names = data.get('vm_names', [])
        
        if not vm_names:
            return jsonify({'success': False, 'message': '缺少虚拟机名称'})
        
        deleted_vms = []
        failed_vms = []
        
        for vm_name in vm_names:
            try:
                # 查找虚拟机文件
                vm_file = find_vm_file(vm_name)
                if not vm_file:
                    failed_vms.append(f'{vm_name} (找不到文件)')
                    continue
                
                # 先停止虚拟机
                vmrun_path = get_vmrun_path()
                
                # 停止虚拟机
                stop_cmd = [vmrun_path, 'stop', vm_file, 'hard']
                subprocess.run(stop_cmd, capture_output=True, text=True, timeout=30)
                
                # 删除虚拟机文件夹
                vm_dir = os.path.dirname(vm_file)
                if os.path.exists(vm_dir):
                    import shutil
                    shutil.rmtree(vm_dir)
                    deleted_vms.append(vm_name)
                    print(f"[DEBUG] 成功删除虚拟机: {vm_name}")
                else:
                    failed_vms.append(f'{vm_name} (文件夹不存在)')
                    
            except Exception as e:
                failed_vms.append(f'{vm_name} ({str(e)})')
                print(f"[DEBUG] 删除虚拟机失败 {vm_name}: {str(e)}")
        
        return jsonify({
            'success': True,
            'deleted_vms': deleted_vms,
            'failed_vms': failed_vms,
            'message': f'成功删除 {len(deleted_vms)} 个虚拟机，失败 {len(failed_vms)} 个'
        })
        
    except Exception as e:
        print(f"[DEBUG] 删除虚拟机API失败: {str(e)}")
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})

def get_vm_status(vm_path):
    """获取虚拟机状态"""
    try:
        vmrun_path = get_vmrun_path()
        
        print(f"[DEBUG] 使用vmrun路径: {vmrun_path}")
        list_cmd = [vmrun_path, 'list']
        print(f"[DEBUG] 执行命令: {' '.join(list_cmd)}")
        
        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30)
        
        print(f"[DEBUG] vmrun list命令返回码: {result.returncode}")
        print(f"[DEBUG] vmrun list命令输出: {result.stdout}")
        if result.stderr:
            print(f"[DEBUG] vmrun list命令错误: {result.stderr}")
        
        if result.returncode == 0:
            running_vms = result.stdout.strip().split('\n')[1:]  # 跳过标题行
            vm_name = os.path.splitext(os.path.basename(vm_path))[0]
            print(f"[DEBUG] 查找虚拟机名称: {vm_name}")
            print(f"[DEBUG] 运行中的虚拟机列表: {running_vms}")
            
            # 检查虚拟机是否在运行列表中
            vm_found = False
            for vm in running_vms:
                if vm.strip() and vm_name in vm:
                    print(f"[DEBUG] 找到运行中的虚拟机: {vm}")
                    vm_found = True
                    break
            
            if vm_found:
                # 检查虚拟机是否正在启动过程中
                try:
                    # 尝试获取虚拟机IP，如果获取失败可能正在启动
                    vm_ip = get_vm_ip(vm_name)
                    if vm_ip and is_valid_ip(vm_ip):
                        print(f"[DEBUG] 虚拟机IP正常: {vm_ip}")
                        return 'running'
                    else:
                        print(f"[DEBUG] 虚拟机IP获取失败，可能正在启动")
                        return 'starting'
                except Exception as e:
                    print(f"[DEBUG] 获取虚拟机IP异常，可能正在启动: {str(e)}")
                    return 'starting'
            else:
                print(f"[DEBUG] 未找到运行中的虚拟机: {vm_name}")
                return 'stopped'
        
        return 'stopped'
        
    except Exception as e:
        print(f"[DEBUG] 获取虚拟机状态失败: {str(e)}")
        return 'unknown'

def get_vm_ip(vm_name):
    """获取虚拟机IP地址，优先用vmrun getGuestIPAddress"""
    logger.debug(f"开始获取虚拟机 {vm_name} 的IP地址")
    try:
        # 1. 通过vmrun getGuestIPAddress
        vm_file = find_vm_file(vm_name)
        if vm_file:
            logger.debug(f"找到虚拟机文件: {vm_file}")
            vmrun_path = get_vmrun_path()
            logger.debug(f"使用备用vmrun路径: {vmrun_path}")
            
            if os.path.exists(vmrun_path):
                try:
                    cmd = [vmrun_path, 'getGuestIPAddress', vm_file, '-wait']
                    logger.debug(f"执行vmrun命令: {cmd}")
                    print(f"[DEBUG] 执行vmrun getGuestIPAddress命令: {' '.join(cmd)}")
                    
                    # 记录命令开始时间
                    start_time = datetime.datetime.now()
                    print(f"[DEBUG] getGuestIPAddress命令开始时间: {start_time}")
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    # 记录命令结束时间
                    end_time = datetime.datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    print(f"[DEBUG] getGuestIPAddress命令结束时间: {end_time}")
                    print(f"[DEBUG] getGuestIPAddress命令执行时长: {duration} 秒")
                    print(f"[DEBUG] getGuestIPAddress命令返回码: {result.returncode}")
                    print(f"[DEBUG] getGuestIPAddress命令输出: {result.stdout}")
                    if result.stderr:
                        print(f"[DEBUG] getGuestIPAddress命令错误: {result.stderr}")
                    
                    if result.returncode == 0:
                        ip = result.stdout.strip()
                        logger.debug(f"vmrun返回IP: {ip}")
                        print(f"[DEBUG] vmrun返回IP: {ip}")
                        if is_valid_ip(ip):
                            logger.info(f"通过vmrun成功获取IP: {ip}")
                            print(f"[DEBUG] IP格式有效: {ip}")
                            return ip
                        else:
                            logger.warning(f"vmrun返回的IP格式无效: {ip}")
                            print(f"[DEBUG] IP格式无效: {ip}")
                    else:
                        logger.warning(f"vmrun命令执行失败，返回码: {result.returncode}, 错误: {result.stderr}")
                        print(f"[DEBUG] vmrun命令执行失败，返回码: {result.returncode}, 错误: {result.stderr}")
                except Exception as e:
                    logger.error(f"vmrun getGuestIPAddress 获取IP失败: {str(e)}")
                    print(f"[DEBUG] vmrun getGuestIPAddress 获取IP失败: {str(e)}")
            else:
                logger.warning(f"vmrun路径不存在: {vmrun_path}")
        else:
            logger.warning(f"未找到虚拟机文件: {vm_name}")
        
        # 2. 兜底：从VMX文件读取
        if vm_file and os.path.exists(vm_file):
            logger.debug(f"尝试从VMX文件读取IP: {vm_file}")
            try:
                with open(vm_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')
                    for line in lines:
                        if 'ip=' in line.lower() or 'ipaddress=' in line.lower():
                            ip = line.split('=')[1].strip().strip('"')
                            logger.debug(f"从VMX文件找到IP配置: {ip}")
                            if is_valid_ip(ip):
                                logger.info(f"从VMX文件成功获取IP: {ip}")
                                return ip
                            else:
                                logger.warning(f"VMX文件中的IP格式无效: {ip}")
            except Exception as e:
                logger.error(f"从VMX文件读取IP失败: {str(e)}")
        
        logger.warning(f"无法获取虚拟机 {vm_name} 的IP地址")
        return None
    except Exception as e:
        logger.error(f"获取虚拟机IP失败: {str(e)}")
        return None

def is_valid_ip(ip):
    """验证IP地址格式"""
    if not ip:
        return False
    
    try:
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        
        for part in parts:
            if not part.isdigit():
                return False
            num = int(part)
            if num < 0 or num > 255:
                return False
        
        return True
    except:
        return False

def get_vm_ip_status(vm_name):
    """获取虚拟机IP状态信息"""
    logger.debug(f"开始获取虚拟机 {vm_name} 的IP状态")
    try:
        ip = get_vm_ip(vm_name)
        if not ip:
            logger.warning(f"虚拟机 {vm_name} 未获取到IP地址")
            return {
                'ip': None,
                'status': 'no_ip',
                'message': '未获取到IP地址'
            }
        
        logger.debug(f"虚拟机 {vm_name} IP地址: {ip}")
        
        # 检查IP连通性
        ping_result = check_ip_connectivity(ip)
        
        if ping_result['success']:
            logger.info(f"虚拟机 {vm_name} IP {ip} 可达")
            return {
                'ip': ip,
                'status': 'online',
                'message': 'IP地址可达',
                'response_time': ping_result.get('response_time')
            }
        else:
            logger.warning(f"虚拟机 {vm_name} IP {ip} 不可达: {ping_result.get('error')}")
            return {
                'ip': ip,
                'status': 'offline',
                'message': 'IP地址不可达',
                'error': ping_result.get('error')
            }
            
    except Exception as e:
        logger.error(f"获取虚拟机 {vm_name} IP状态失败: {str(e)}")
        return {
            'ip': None,
            'status': 'error',
            'message': f'获取IP状态失败: {str(e)}'
        }

def check_ip_connectivity(ip):
    """检查IP地址连通性"""
    logger.debug(f"开始检查IP连通性: {ip}")
    try:
        # 使用ping命令检查连通性
        ping_cmd = ['ping', '-n', '1', '-w', '3000', ip]
        logger.debug(f"执行ping命令: {ping_cmd}")
        result = subprocess.run(ping_cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            # 解析响应时间
            response_time = None
            for line in result.stdout.split('\n'):
                if '时间=' in line or 'time=' in line.lower():
                    try:
                        time_str = line.split('时间=')[1].split('ms')[0].strip()
                        response_time = int(time_str)
                        logger.debug(f"解析到响应时间: {response_time}ms")
                    except:
                        logger.debug("响应时间解析失败")
                        pass
                    break
            
            logger.debug(f"IP {ip} 连通性检查成功，响应时间: {response_time}ms")
            return {
                'success': True,
                'response_time': response_time
            }
        else:
            logger.warning(f"IP {ip} ping失败，返回码: {result.returncode}")
            return {
                'success': False,
                'error': 'ping失败'
            }
            
    except subprocess.TimeoutExpired:
        logger.error(f"IP {ip} 连接超时")
        return {
            'success': False,
            'error': '连接超时'
        }
    except Exception as e:
        logger.error(f"IP {ip} 连通性检查异常: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def get_wuma_info(vm_name):
    """获取虚拟机五码信息"""
    try:
        # 检查plist目录中是否有对应的五码文件
        plist_dir = os.path.join(os.path.dirname(__file__), '..', 'plist')
        if os.path.exists(plist_dir):
            # 查找与虚拟机名称相关的plist文件
            for file in os.listdir(plist_dir):
                if file.endswith('.plist') and vm_name.lower() in file.lower():
                    return f"已配置五码信息"
            
            # 检查是否有通用的五码配置文件
            for file in os.listdir(plist_dir):
                if file.endswith('.plist') and 'wuma' in file.lower():
                    return f"通用五码配置"
        
        # 如果没有找到五码信息，返回None
        return None
        
    except Exception as e:
        print(f"[DEBUG] 获取五码信息失败: {str(e)}")
        return None

def check_ssh_status(ip):
    """检查SSH连接状态"""
    if not ip:
        return 'offline'
    
    try:
        # 简单的ping测试
        result = subprocess.run(['ping', '-n', '1', ip], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return 'online'
        else:
            return 'offline'
            
    except Exception as e:
        print(f"[DEBUG] SSH状态检查失败: {str(e)}")
        return 'offline'

def check_ssh_port_open(ip, port=22):
    """检查SSH端口是否开放"""
    if not ip:
        return False
    
    try:
        import socket
        
        # 创建socket连接
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)  # 3秒超时
        
        # 尝试连接SSH端口
        result = sock.connect_ex((ip, port))
        sock.close()
        
        if result == 0:
            logger.debug(f"SSH端口 {port} 开放: {ip}")
            return True
        else:
            logger.debug(f"SSH端口 {port} 未开放: {ip}")
            return False
            
    except Exception as e:
        logger.debug(f"检查SSH端口失败: {str(e)}")
        return False

def check_ssh_trust_status(ip, username=vm_username):
    """检查SSH互信状态"""
    if not ip:
        return False
    
    try:
        import paramiko
        
        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # 尝试无密码连接
        ssh.connect(ip, username=username, timeout=5)
        ssh.close()
        return True
        
    except Exception as e:
        logger.debug(f"SSH互信检查失败: {str(e)}")
        return False

def get_vm_online_status(vm_name):
    """获取虚拟机在线状态（新逻辑：根据虚拟机状态和网络连接情况综合判断）"""
    logger.debug(f"检查虚拟机 {vm_name} 的在线状态（新逻辑）")
    
    try:
        # 1. 检查虚拟机是否运行
        vm_file = find_vm_file(vm_name)
        if not vm_file:
            logger.warning(f"未找到虚拟机文件: {vm_name}")
            return {
                'status': 'offline',
                'reason': '虚拟机文件不存在',
                'ip': None,
                'ssh_trust': False,
                'ssh_port_open': False,
                'vm_status': 'unknown'
            }
        
        vm_status = get_vm_status(vm_file)
        logger.debug(f"虚拟机 {vm_name} 状态: {vm_status}")
        print(f"[DEBUG] 虚拟机 {vm_name} 状态检测结果: {vm_status}")
        
        # 2. 根据虚拟机状态进行初步判断
        if vm_status == 'stopped':
            logger.debug(f"虚拟机 {vm_name} 已关机")
            return {
                'status': 'offline',
                'reason': '虚拟机关机',
                'ip': None,
                'ssh_trust': False,
                'ssh_port_open': False,
                'vm_status': vm_status
            }
        elif vm_status in ['suspended', 'paused']:
            logger.debug(f"虚拟机 {vm_name} 处于挂起状态")
            return {
                'status': 'unknown',
                'reason': f'虚拟机{vm_status}状态',
                'ip': None,
                'ssh_trust': False,
                'ssh_port_open': False,
                'vm_status': vm_status
            }
        elif vm_status == 'unknown':
            logger.debug(f"虚拟机 {vm_name} 状态未知，继续检查网络连接")
            # 状态未知时，继续检查网络连接情况
        elif vm_status != 'running':
            logger.debug(f"虚拟机 {vm_name} 状态异常: {vm_status}")
            return {
                'status': 'unknown',
                'reason': f'虚拟机状态异常: {vm_status}',
                'ip': None,
                'ssh_trust': False,
                'ssh_port_open': False,
                'vm_status': vm_status
            }
        
        # 3. 虚拟机运行中或状态未知，检查网络连接情况
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            logger.debug(f"虚拟机 {vm_name} 无法获取IP地址")
            print(f"[DEBUG] 虚拟机 {vm_name} IP地址获取失败")
            return {
                'status': 'unknown',
                'reason': '无法获取IP地址',
                'ip': None,
                'ssh_trust': False,
                'ssh_port_open': False,
                'vm_status': vm_status
            }
        
        logger.debug(f"虚拟机 {vm_name} IP地址获取成功: {vm_ip}")
        print(f"[DEBUG] 虚拟机 {vm_name} IP地址获取成功: {vm_ip}")
        
        # 4. 检查IP连通性
        ip_status = check_ip_connectivity(vm_ip)
        print(f"[DEBUG] 虚拟机 {vm_name} IP连通性检查结果: {ip_status}")
        if not ip_status['success']:
            logger.debug(f"虚拟机 {vm_name} IP {vm_ip} 不可达")
            print(f"[DEBUG] 虚拟机 {vm_name} IP {vm_ip} 不可达: {ip_status.get('error', '未知错误')}")
            return {
                'status': 'offline',
                'reason': f'IP不可达: {ip_status.get("error", "未知错误")}',
                'ip': vm_ip,
                'ssh_trust': False,
                'ssh_port_open': False,
                'vm_status': vm_status
            }
        
        # 5. 检查SSH端口是否开放
        ssh_port_open = check_ssh_port_open(vm_ip)
        print(f"[DEBUG] 虚拟机 {vm_name} SSH端口检查结果: {ssh_port_open}")
        
        # 6. 检查SSH互信状态
        ssh_trust_status = check_ssh_trust_status(vm_ip)
        print(f"[DEBUG] 虚拟机 {vm_name} SSH互信检查结果: {ssh_trust_status}")
        
        # 7. 根据三个条件综合判断在线状态
        conditions_met = 0
        total_conditions = 3
        
        if ip_status['success']:
            conditions_met += 1
        if ssh_port_open:
            conditions_met += 1
        if ssh_trust_status:
            conditions_met += 1
        
        logger.debug(f"虚拟机 {vm_name} 条件满足情况: {conditions_met}/{total_conditions}")
        print(f"[DEBUG] 虚拟机 {vm_name} 条件满足情况: {conditions_met}/{total_conditions}")
        
        if conditions_met == total_conditions:
            # 三个条件都满足：完全在线
            status_text = '完全在线'
            reason_text = 'IP可达 + SSH端口开放 + SSH互信成功'
            if vm_status == 'unknown':
                status_text = '完全在线（状态未知）'
                reason_text = 'IP可达 + SSH端口开放 + SSH互信成功（虚拟机状态未知）'
            
            logger.info(f"虚拟机 {vm_name} {status_text}：{reason_text}")
            print(f"[DEBUG] 虚拟机 {vm_name} 三个条件都满足，返回online状态")
            return {
                'status': 'online',
                'reason': reason_text,
                'ip': vm_ip,
                'ssh_trust': True,
                'ssh_port_open': True,
                'vm_status': vm_status
            }
        elif conditions_met > 0:
            # 部分条件满足：部分在线
            missing_conditions = []
            if not ip_status['success']:
                missing_conditions.append('IP不可达')
            if not ssh_port_open:
                missing_conditions.append('SSH端口未开放')
            if not ssh_trust_status:
                missing_conditions.append('SSH互信未设置')
            
            status_text = '部分在线'
            reason = f'部分在线（缺少: {", ".join(missing_conditions)}）'
            if vm_status == 'unknown':
                status_text = '部分在线（状态未知）'
                reason = f'部分在线（缺少: {", ".join(missing_conditions)}，虚拟机状态未知）'
            
            logger.debug(f"虚拟机 {vm_name} {reason}")
            return {
                'status': 'partial',
                'reason': reason,
                'ip': vm_ip,
                'ssh_trust': ssh_trust_status,
                'ssh_port_open': ssh_port_open,
                'vm_status': vm_status
            }
        else:
            # 没有条件满足：未在线
            status_text = '未在线'
            reason_text = '所有网络条件都不满足'
            if vm_status == 'unknown':
                status_text = '未在线（状态未知）'
                reason_text = '所有网络条件都不满足（虚拟机状态未知）'
            
            logger.debug(f"虚拟机 {vm_name} {status_text}：{reason_text}")
            return {
                'status': 'offline',
                'reason': reason_text,
                'ip': vm_ip,
                'ssh_trust': False,
                'ssh_port_open': False,
                'vm_status': vm_status
            }
            
    except Exception as e:
        logger.error(f"检查虚拟机 {vm_name} 在线状态时出错: {str(e)}")
        return {
            'status': 'error',
            'reason': f'检查状态时出错: {str(e)}',
            'ip': None,
            'ssh_trust': False,
            'ssh_port_open': False,
            'vm_status': 'unknown'
        }

def find_vm_file(vm_name):
    """查找虚拟机文件"""
    vm_dir = r'D:\macos_vm\NewVM'
    if os.path.exists(vm_dir):
        for root, dirs, files in os.walk(vm_dir):
            for file in files:
                if file.endswith('.vmx') and vm_name in file:
                    return os.path.join(root, file)
    return None

def get_vm_snapshots(vm_path):
    """获取虚拟机快照列表"""
    try:
        vmrun_path = get_vmrun_path()
        
        snapshots_cmd = [vmrun_path, 'listSnapshots', vm_path]
        result = subprocess.run(snapshots_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return result.stdout.strip().split('\n')
        else:
            return []
            
    except Exception as e:
        print(f"[DEBUG] 获取快照列表失败: {str(e)}")
        return []

def get_vm_config(vm_path):
    """获取虚拟机配置信息"""
    try:
        with open(vm_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        config = {}
        for line in content.split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip().strip('"')
        
        return config
        
    except Exception as e:
        print(f"[DEBUG] 获取虚拟机配置失败: {str(e)}")
        return {}

@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/scripts')
@login_required
def api_scripts():
    """获取脚本文件列表（支持分页）"""
    logger.info("收到获取脚本列表请求")
    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 5, type=int)  # 修改默认分页大小为5
        
        logger.info(f"收到分页请求: page={page}, page_size={page_size}")
        logger.info(f"请求参数: {dict(request.args)}")
        
        scripts_dir = r'D:\macos_vm\macos_sh'
        scripts = []
        
        if os.path.exists(scripts_dir):
            for filename in os.listdir(scripts_dir):
                if filename.endswith('.sh'):
                    file_path = os.path.join(scripts_dir, filename)
                    try:
                        # 获取文件信息
                        stat = os.stat(file_path)
                        size = stat.st_size
                        modified_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        
                        # 格式化文件大小
                        if size < 1024:
                            size_str = f"{size}B"
                        elif size < 1024 * 1024:
                            size_str = f"{size // 1024}KB"
                        else:
                            size_str = f"{size // (1024 * 1024)}MB"
                        
                        # 尝试读取脚本备注（从同名的.txt文件）
                        note_file = file_path.replace('.sh', '.txt')
                        note = ""
                        if os.path.exists(note_file):
                            try:
                                with open(note_file, 'r', encoding='utf-8') as f:
                                    note = f.read().strip()
                            except Exception as e:
                                logger.warning(f"读取备注文件失败 {note_file}: {str(e)}")
                        
                        scripts.append({
                            'name': filename,
                            'size': size_str,
                            'modified_time': modified_time,
                            'path': file_path,
                            'note': note
                        })
                        
                        logger.debug(f"找到脚本文件: {filename}, 大小: {size_str}, 修改时间: {modified_time}")
                        
                    except Exception as e:
                        logger.error(f"处理脚本文件 {filename} 时出错: {str(e)}")
                        continue
            
            # 按文件名排序
            scripts.sort(key=lambda x: x['name'])
            
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
            logger.info(f"返回的pagination数据: {{'current_page': {page}, 'page_size': {page_size}, 'total_count': {total_count}, 'total_pages': {total_pages}, 'start_index': {start_index}, 'end_index': {actual_end_index}}}")
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
        else:
            logger.warning(f"脚本目录不存在: {scripts_dir}")
            return jsonify({
                'success': False,
                'message': f'脚本目录不存在: {scripts_dir}'
            })
            
    except Exception as e:
        logger.error(f"获取脚本列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取脚本列表失败: {str(e)}'
        })

@app.route('/api/scripts/all')
@login_required
def api_all_scripts():
    """获取所有脚本文件列表（不分页）"""
    logger.info("收到获取所有脚本列表请求")
    try:
        scripts_dir = r'D:\macos_vm\macos_sh'
        scripts = []
        
        if os.path.exists(scripts_dir):
            for filename in os.listdir(scripts_dir):
                if filename.endswith('.sh'):
                    file_path = os.path.join(scripts_dir, filename)
                    try:
                        # 获取文件信息
                        stat = os.stat(file_path)
                        size = stat.st_size
                        modified_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        
                        # 格式化文件大小
                        if size < 1024:
                            size_str = f"{size}B"
                        elif size < 1024 * 1024:
                            size_str = f"{size // 1024}KB"
                        else:
                            size_str = f"{size // (1024 * 1024)}MB"
                        
                        # 尝试读取脚本备注（从同名的.txt文件）
                        note_file = file_path.replace('.sh', '.txt')
                        note = ""
                        if os.path.exists(note_file):
                            try:
                                with open(note_file, 'r', encoding='utf-8') as f:
                                    note = f.read().strip()
                            except Exception as e:
                                logger.warning(f"读取备注文件失败 {note_file}: {str(e)}")
                        
                        scripts.append({
                            'name': filename,
                            'size': size_str,
                            'modified_time': modified_time,
                            'path': file_path,
                            'note': note
                        })
                        
                        logger.debug(f"找到脚本文件: {filename}, 大小: {size_str}, 修改时间: {modified_time}")
                        
                    except Exception as e:
                        logger.error(f"处理脚本文件 {filename} 时出错: {str(e)}")
                        continue
            
            # 按文件名排序
            scripts.sort(key=lambda x: x['name'])
            
            logger.info(f"成功获取 {len(scripts)} 个脚本文件")
            return jsonify({
                'success': True,
                'scripts': scripts
            })
        else:
            logger.warning(f"脚本目录不存在: {scripts_dir}")
            return jsonify({
                'success': False,
                'message': f'脚本目录不存在: {scripts_dir}'
            })
            
    except Exception as e:
        logger.error(f"获取所有脚本列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取所有脚本列表失败: {str(e)}'
        })

@app.route('/api/script/add', methods=['POST'])
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
        import re
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
        
        scripts_dir = r'D:\macos_vm\macos_sh'
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

@app.route('/api/script/edit', methods=['POST'])
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
        
        scripts_dir = r'D:\macos_vm\macos_sh'
        script_path = os.path.join(scripts_dir, script_name)
        note_path = script_path.replace('.sh', '.txt')
        
        if not os.path.exists(script_path):
            return jsonify({
                'success': False,
                'message': f'脚本文件不存在: {script_name}'
            })
        
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

@app.route('/api/script/delete', methods=['POST'])
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
        
        scripts_dir = r'D:\macos_vm\macos_sh'
        script_path = os.path.join(scripts_dir, script_name)
        note_path = script_path.replace('.sh', '.txt')
        
        # 检查脚本文件是否存在
        if not os.path.exists(script_path):
            return jsonify({
                'success': False,
                'message': f'脚本文件不存在: {script_name}'
            })
        
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

@app.route('/api/script/content/<script_name>')
@login_required
def api_get_script_content(script_name):
    """获取脚本内容"""
    logger.info(f"获取脚本内容: {script_name}")
    try:
        scripts_dir = r'D:\macos_vm\macos_sh'
        script_path = os.path.join(scripts_dir, script_name)
        note_path = script_path.replace('.sh', '.txt')
        
        if not os.path.exists(script_path):
            return jsonify({
                'success': False,
                'message': f'脚本文件不存在: {script_name}'
            })
        
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

@app.route('/api/vm_send_script', methods=['POST'])
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
        
        # 检查脚本文件是否存在
        scripts_dir = r'D:\macos_vm\macos_sh'
        script_path = os.path.join(scripts_dir, script_name)
        
        if not os.path.exists(script_path):
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
            
            # 使用scp发送脚本
            import subprocess
            scp_cmd = [
                'scp',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'ConnectTimeout=10',
                script_path,
                f"{vm_username}@{vm_info['ip']}:{script_remote_path}{script_name}"
            ]
            
            logger.debug(f"执行SCP命令: {' '.join(scp_cmd)}")
            result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"脚本发送成功到虚拟机 {vm_name} ({vm_info['ip']})")
                return jsonify({
                    'success': True,
                    'message': f'脚本 {script_name} 发送成功到虚拟机 {vm_name}',
                    'file_path': f'{script_remote_path}{script_name}'
                })
            else:
                error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                logger.error(f"脚本发送失败到虚拟机 {vm_name}: {error_msg}")
                
                # 根据错误类型提供更详细的错误信息
                if 'Permission denied' in error_msg:
                    error_detail = 'SSH认证失败，请检查SSH互信设置'
                elif 'Connection refused' in error_msg:
                    error_detail = 'SSH连接被拒绝，请检查SSH服务是否运行'
                elif 'No route to host' in error_msg:
                    error_detail = '无法连接到主机，请检查网络连接'
                else:
                    error_detail = f'SCP传输失败: {error_msg}'
                
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

@app.route('/api/vm_add_permissions', methods=['POST'])
@login_required
def api_vm_add_permissions():
    """为虚拟机上的脚本添加执行权限"""
    logger.info("收到添加脚本执行权限API请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        script_names = data.get('script_names', [])
        username = data.get('username', vm_username)
        
        logger.debug(f"添加执行权限参数 - 虚拟机: {vm_name}, 脚本: {script_names}, 用户: {username}")
        
        if not vm_name:
            logger.warning("虚拟机名称不能为空")
            return jsonify({'success': False, 'message': '虚拟机名称不能为空'})
        
        if not script_names or len(script_names) == 0:
            logger.warning("脚本名称列表不能为空")
            return jsonify({'success': False, 'message': '脚本名称列表不能为空'})
        
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

@app.route('/api/ssh_trust', methods=['POST'])
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
        
        # 设置SSH互信
        success, message = setup_ssh_trust(vm_ip, username, password)
        
        if success:
            logger.info(f"SSH互信设置成功: {message}")
            return jsonify({'success': True, 'message': message})
        else:
            logger.error(f"SSH互信设置失败: {message}")
            return jsonify({'success': False, 'message': message})
            
    except Exception as e:
        logger.error(f"SSH互信设置异常: {str(e)}")
        return jsonify({'success': False, 'message': f'设置SSH互信时发生错误: {str(e)}'})

def setup_ssh_trust(ip, username, password):
    """设置SSH互信的具体实现"""
    logger.info(f"开始设置SSH互信 - IP: {ip}, 用户: {username}")
    try:
        # 1. 生成SSH密钥对（如果不存在）
        ssh_key_path = os.path.expanduser('~/.ssh/id_rsa')
        ssh_pub_key_path = os.path.expanduser('~/.ssh/id_rsa.pub')
        
        # 确保.ssh目录存在
        ssh_dir = os.path.expanduser('~/.ssh')
        if not os.path.exists(ssh_dir):
            os.makedirs(ssh_dir, mode=0o700)
            logger.debug(f"创建SSH目录: {ssh_dir}")
        
        if not os.path.exists(ssh_key_path):
            logger.info("生成SSH密钥对")
            # 生成SSH密钥对
            keygen_cmd = ['ssh-keygen', '-t', 'rsa', '-b', '2048', '-f', ssh_key_path, '-N', '']
            logger.debug(f"执行ssh-keygen命令: {keygen_cmd}")
            result = subprocess.run(keygen_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"生成SSH密钥失败: {result.stderr}")
                return False, f"生成SSH密钥失败: {result.stderr}"
            else:
                logger.debug("SSH密钥生成成功")
        
        # 2. 读取公钥
        if not os.path.exists(ssh_pub_key_path):
            logger.error("SSH公钥文件不存在")
            return False, "SSH公钥文件不存在"
        
        with open(ssh_pub_key_path, 'r') as f:
            public_key = f.read().strip()
        
        logger.debug("读取公钥成功")
        
        # 3. 使用paramiko库设置SSH互信（推荐方法）
        try:
            import paramiko
            
            # 创建SSH客户端
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接到远程主机
            logger.debug(f"尝试连接到 {ip}")
            ssh.connect(ip, username=username, password=password, timeout=10)
            logger.debug("SSH连接成功")
            
            # 创建.ssh目录
            stdin, stdout, stderr = ssh.exec_command('mkdir -p ~/.ssh')
            exit_status = stdout.channel.recv_exit_status()
            logger.debug(f"创建.ssh目录状态: {exit_status}")
            
            # 添加公钥到authorized_keys
            stdin, stdout, stderr = ssh.exec_command(f'echo "{public_key}" >> ~/.ssh/authorized_keys')
            exit_status = stdout.channel.recv_exit_status()
            logger.debug(f"添加公钥状态: {exit_status}")
            
            # 设置正确的权限
            stdin, stdout, stderr = ssh.exec_command('chmod 700 ~/.ssh')
            stdin, stdout, stderr = ssh.exec_command('chmod 600 ~/.ssh/authorized_keys')
            logger.debug("设置SSH目录权限完成")
            
            # 验证设置是否成功
            stdin, stdout, stderr = ssh.exec_command('cat ~/.ssh/authorized_keys')
            authorized_keys_content = stdout.read().decode().strip()
            
            ssh.close()
            
            if public_key in authorized_keys_content:
                logger.info("SSH互信设置成功（使用paramiko）")
                return True, "SSH互信设置成功"
            else:
                logger.error("公钥未正确添加到authorized_keys")
                return False, "公钥未正确添加到authorized_keys"
            
        except ImportError:
            logger.error("paramiko库未安装")
            return False, "需要安装paramiko库: pip install paramiko"
        except Exception as e:
            logger.error(f"paramiko方法失败: {str(e)}")
            return False, f"SSH连接失败: {str(e)}"
        
    except Exception as e:
        logger.error(f"setup_ssh_trust异常: {str(e)}")
        return False, f"设置SSH互信时发生错误: {str(e)}"

@app.route('/api/vm_chmod_scripts', methods=['POST'])
@login_required
def api_vm_chmod_scripts():
    """为虚拟机上的指定脚本或所有sh脚本添加执行权限"""
    logger.info("收到为脚本添加执行权限API请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        script_names = data.get('script_names', [])  # 可以传入单个脚本名或脚本名列表
        username = data.get('username', vm_username)
        
        logger.debug(f"添加执行权限参数 - 虚拟机: {vm_name}, 脚本: {script_names}, 用户: {username}")
        
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

def execute_chmod_scripts(ip, username, script_names=None):
    """远程执行chmod +x命令"""
    logger.info(f"开始为IP {ip} 的用户 {username} 添加脚本执行权限")
    try:
        import paramiko
        
        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # 连接到远程主机（使用SSH互信，无需密码）
        logger.debug(f"尝试连接到 {ip}")
        ssh.connect(ip, username=username, timeout=10)
        logger.debug("SSH连接成功")
        
        # 根据传入的脚本名决定执行方式
        if script_names and len(script_names) > 0:
            # 为指定脚本添加执行权限
            commands = ["cd ~"]  # 切换到用户家目录
            
            for script_name in script_names:
                # 确保脚本名以.sh结尾
                if not script_name.endswith('.sh'):
                    script_name += '.sh'
                commands.append(f"chmod +x {script_name}")
            
            # 列出指定脚本的权限
            script_list = " ".join([name if name.endswith('.sh') else name + '.sh' for name in script_names])
            commands.append(f"ls -la {script_list} 2>/dev/null || echo '没有找到指定的脚本文件'")
            
            logger.debug(f"为指定脚本添加执行权限: {script_names}")
        else:
            # 为所有sh脚本添加执行权限
            commands = [
                "cd ~",  # 切换到用户家目录
                "chmod +x *.sh",  # 为所有sh脚本添加执行权限
                "ls -la *.sh 2>/dev/null || echo '没有找到.sh文件'"  # 列出所有sh文件及其权限
            ]
            logger.debug("为所有.sh文件添加执行权限")
        
        results = []
        for cmd in commands:
            logger.debug(f"执行命令: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            logger.debug(f"命令 '{cmd}' 执行状态: {exit_status}")
            if output:
                logger.debug(f"输出: {output}")
            if error:
                logger.debug(f"错误: {error}")
            
            results.append({
                'command': cmd,
                'exit_status': exit_status,
                'output': output,
                'error': error
            })
        
        ssh.close()
        
        # 检查执行结果
        chmod_commands = [r for r in results if r['command'].startswith('chmod')]
        ls_result = results[-1]  # 最后一个命令是ls
        
        # 检查所有chmod命令是否成功
        failed_chmods = [r for r in chmod_commands if r['exit_status'] != 0]
        
        if not failed_chmods:
            logger.info("chmod命令执行成功")
            if script_names and len(script_names) > 0:
                message = f"成功为指定脚本添加执行权限: {', '.join(script_names)}\n"
            else:
                message = "成功为家目录下的所有.sh文件添加执行权限\n"
            
            if ls_result['output'] and ls_result['output'] != '没有找到.sh文件' and ls_result['output'] != '没有找到指定的脚本文件':
                message += f"文件列表:\n{ls_result['output']}"
            else:
                message += "未找到指定的脚本文件"
            return True, message
        else:
            logger.error(f"部分chmod命令执行失败: {failed_chmods}")
            error_messages = [f"{r['command']}: {r['error']}" for r in failed_chmods]
            return False, f"部分脚本执行权限设置失败: {'; '.join(error_messages)}"
        
    except ImportError:
        logger.error("paramiko库未安装")
        return False, "需要安装paramiko库: pip install paramiko"
    except Exception as e:
        logger.error(f"execute_chmod_scripts异常: {str(e)}")
        return False, f"远程执行chmod命令时发生错误: {str(e)}"

@app.route('/vm_script_send')
@login_required
def vm_script_send_page():
    """发送脚本页面"""
    logger.debug("访问发送脚本页面")
    return render_template('vm_script_send.html')

@app.route('/api/get_wuma_info', methods=['POST'])
@login_required
def api_get_wuma_info():
    """获取五码信息API - 通过SSH互信执行家目录脚本"""
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        
        if not vm_name:
            return jsonify({'success': False, 'error': '缺少虚拟机名称参数'})
        
        logger.debug(f"开始获取虚拟机 {vm_name} 的五码信息")
        
        # 获取虚拟机IP地址
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip or vm_ip == '获取中...' or vm_ip == '-':
            return jsonify({'success': False, 'error': f'无法获取虚拟机 {vm_name} 的IP地址'})
        
        logger.debug(f"虚拟机 {vm_name} 的IP地址: {vm_ip}")
        
        # 通过SSH互信执行家目录脚本
        result = execute_remote_script(vm_ip, 'wx', 'run_debug_wuma.sh')
        if len(result) == 3:
            success, output, ssh_log = result
        elif len(result) == 2:
            success, output = result
        else:
            success, output = False, "未知错误"
        
        if success:
            logger.info(f"成功获取虚拟机 {vm_name} 的五码信息")
            return jsonify({'success': True, 'output': output})
        else:
            logger.error(f"获取虚拟机 {vm_name} 的五码信息失败: {output}")
            return jsonify({'success': False, 'error': output})
            
    except Exception as e:
        logger.error(f"获取五码信息时发生异常: {str(e)}")
        return jsonify({'success': False, 'error': f'获取五码信息时发生异常: {str(e)}'})

@app.route('/api/get_ju_info', methods=['POST'])
@login_required
def api_get_ju_info():
    """获取JU值信息API - 通过SSH互信执行家目录脚本"""
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        
        if not vm_name:
            return jsonify({'success': False, 'error': '缺少虚拟机名称参数'})
        
        logger.debug(f"开始获取虚拟机 {vm_name} 的JU值信息")
        
        # 获取虚拟机IP地址
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip or vm_ip == '获取中...' or vm_ip == '-':
            return jsonify({'success': False, 'error': f'无法获取虚拟机 {vm_name} 的IP地址'})
        
        logger.debug(f"虚拟机 {vm_name} 的IP地址: {vm_ip}")
        
        # 通过SSH互信执行家目录脚本
        result = execute_remote_script(vm_ip, 'wx', 'run_debug_ju.sh')
        if len(result) == 3:
            success, output, ssh_log = result
        elif len(result) == 2:
            success, output = result
        else:
            success, output = False, "未知错误"
        
        if success:
            logger.info(f"成功获取虚拟机 {vm_name} 的JU值信息")
            return jsonify({'success': True, 'output': output})
        else:
            logger.error(f"获取虚拟机 {vm_name} 的JU值信息失败: {output}")
            return jsonify({'success': False, 'error': output})
            
    except Exception as e:
        logger.error(f"获取JU值信息时发生异常: {str(e)}")
        return jsonify({'success': False, 'error': f'获取JU值信息时发生异常: {str(e)}'})

def execute_remote_script(ip, username, script_name):
    """通过SSH互信执行家目录脚本并获取输出"""
    try:
        import paramiko
        
        # 构建详细的SSH调用日志
        ssh_log = []
        ssh_log.append(f"[SSH] 开始连接到远程主机: {ip}")
        ssh_log.append(f"[SSH] 用户名: {username}")
        ssh_log.append(f"[SSH] 目标脚本: {script_name}")
        
        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_log.append("[SSH] SSH客户端创建成功")
        
        # 通过SSH互信连接到远程主机（无需密码）
        ssh_log.append(f"[SSH] 正在建立SSH连接...")
        ssh.connect(ip, username=username, timeout=10)
        ssh_log.append("[SSH] SSH连接建立成功")
        
        # 检查脚本是否存在
        check_command = f"ls -la ~/{script_name}"
        ssh_log.append(f"[SSH] 检查脚本是否存在: {check_command}")
        stdin, stdout, stderr = ssh.exec_command(check_command)
        check_output = stdout.read().decode().strip()
        check_error = stderr.read().decode().strip()
        
        if not check_output:
            ssh_log.append(f"[SSH] 脚本不存在: ~/{script_name}")
            ssh.close()
            return False, f"脚本 ~/{script_name} 不存在", "\n".join(ssh_log)
        
        ssh_log.append(f"[SSH] 脚本存在: {check_output}")
        
        # 检查脚本执行权限
        chmod_command = f"chmod +x ~/{script_name}"
        ssh_log.append(f"[SSH] 添加执行权限: {chmod_command}")
        stdin, stdout, stderr = ssh.exec_command(chmod_command)
        chmod_error = stderr.read().decode().strip()
        if chmod_error:
            ssh_log.append(f"[SSH] 添加执行权限失败: {chmod_error}")
        else:
            ssh_log.append("[SSH] 执行权限添加成功")
        
        # 执行家目录脚本命令
        command = f"cd ~ && ./{script_name}"
        ssh_log.append(f"[SSH] 执行脚本命令: {command}")
        
        stdin, stdout, stderr = ssh.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        ssh_log.append(f"[SSH] 脚本执行完成，退出状态: {exit_status}")
        
        if output:
            ssh_log.append(f"[SSH] 脚本输出长度: {len(output)} 字符")
        if error:
            ssh_log.append(f"[SSH] 脚本错误输出长度: {len(error)} 字符")
        
        ssh.close()
        ssh_log.append("[SSH] SSH连接已关闭")
        
        # 构建完整的执行日志
        full_log = "\n".join(ssh_log)
        
        if exit_status == 0:
            logger.info(f"脚本 {script_name} 执行成功，输出长度: {len(output)}")
            return True, output, full_log
        else:
            error_msg = error if error else f"脚本 {script_name} 执行失败，退出状态: {exit_status}"
            logger.error(f"脚本 {script_name} 执行失败: {error_msg}")
            return False, error_msg, full_log
            
    except ImportError:
        logger.error("paramiko库未安装")
        return False, "需要安装paramiko库: pip install paramiko", "paramiko库未安装"
    except Exception as e:
        logger.error(f"execute_remote_script异常: {str(e)}")
        error_msg = f"通过SSH互信执行脚本时发生错误: {str(e)}"
        return False, error_msg, f"[SSH] 连接异常: {str(e)}"

# 成品虚拟机API端点 - 使用通用函数

@app.route('/api/vm_chengpin_list')
@login_required
def api_vm_chengpin_list():
    """获取成品虚拟机列表"""
    return get_vm_list_from_directory(VM_DIRS['chengpin'], '成品虚拟机')

@app.route('/api/get_chengpin_wuma_info', methods=['POST'])
@login_required
def api_get_chengpin_wuma_info():
    """获取成品虚拟机五码信息"""
    return get_wuma_info_generic('成品虚拟机')

@app.route('/api/get_chengpin_ju_info', methods=['POST'])
@login_required
def api_get_chengpin_ju_info():
    """获取成品虚拟机JU值信息"""
    return get_ju_info_generic('成品虚拟机')

@app.route('/api/vm_chengpin_online_status', methods=['POST'])
@login_required
def api_vm_chengpin_online_status():
    """获取成品虚拟机在线状态"""
    logger.info("收到获取成品虚拟机在线状态请求")
    try:
        data = request.get_json()
        vm_names = data.get('vm_names', [])
        
        if not vm_names:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称列表'
            })
        
        results = {}
        for vm_name in vm_names:
            try:
                online_status = get_vm_online_status(vm_name)
                results[vm_name] = online_status
                print(f"[DEBUG] 成品虚拟机 {vm_name} 在线状态结果: {online_status}")
            except Exception as e:
                logger.error(f"获取虚拟机 {vm_name} 在线状态失败: {str(e)}")
                print(f"[DEBUG] 成品虚拟机 {vm_name} 获取状态失败: {str(e)}")
                results[vm_name] = {
                    'status': 'error',
                    'reason': f'获取状态失败: {str(e)}',
                    'ip': None,
                    'ssh_trust': False,
                    'ssh_port_open': False,
                    'vm_status': 'unknown'
                }
        
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        logger.error(f"获取成品虚拟机在线状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取成品虚拟机在线状态失败: {str(e)}'
        })

@app.route('/api/ssh_chengpin_trust', methods=['POST'])
@login_required
def api_ssh_chengpin_trust():
    """设置成品虚拟机SSH互信"""
    logger.info("收到设置成品虚拟机SSH互信请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        username = data.get('username', vm_username)
        password = data.get('password', '123456')
        
        if not vm_name:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称参数'
            })
        
        # 获取虚拟机IP
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            return jsonify({
                'success': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址'
            })
        
        # 设置SSH互信
        success, message = setup_ssh_trust(vm_ip, username, password)
        
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        logger.error(f"设置成品虚拟机SSH互信失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'设置成品虚拟机SSH互信失败: {str(e)}'
        })

@app.route('/api/vm_chengpin_delete', methods=['POST'])
@login_required
def api_vm_chengpin_delete():
    """删除成品虚拟机"""
    return delete_vm_generic('成品虚拟机', VM_DIRS['chengpin'])

@app.route('/api/vm_chengpin_start', methods=['POST'])
@login_required
def api_vm_chengpin_start():
    """启动成品虚拟机"""
    return vm_operation_generic('start', '成品虚拟机', VM_DIRS['chengpin'])

@app.route('/api/vm_chengpin_stop', methods=['POST'])
@login_required
def api_vm_chengpin_stop():
    """停止成品虚拟机"""
    return vm_operation_generic('stop', '成品虚拟机', VM_DIRS['chengpin'])

@app.route('/api/vm_chengpin_restart', methods=['POST'])
@login_required
def api_vm_chengpin_restart():
    """重启成品虚拟机"""
    return vm_operation_generic('restart', '成品虚拟机', VM_DIRS['chengpin'])

@app.route('/api/vm_chengpin_info/<vm_name>')
@login_required
def api_vm_chengpin_info(vm_name):
    """获取成品虚拟机详细信息"""
    return get_vm_info_generic(vm_name, '成品虚拟机', VM_DIRS['chengpin'])

@app.route('/api/vm_chengpin_send_script', methods=['POST'])
@login_required
def api_vm_chengpin_send_script():
    """向成品虚拟机发送脚本"""
    return send_script_generic('成品虚拟机')

@app.route('/api/vm_chengpin_add_permissions', methods=['POST'])
@login_required
def api_vm_chengpin_add_permissions():
    """为成品虚拟机添加脚本执行权限"""
    return add_permissions_generic('成品虚拟机')

@app.route('/api/vm_chengpin_chmod_scripts', methods=['POST'])
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
        logger.error(f"为成品虚拟机脚本添加执行权限失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'为成品虚拟机脚本添加执行权限失败: {str(e)}'
        })

@app.route('/api/vm_chengpin_ip_status/<vm_name>')
@login_required
def api_vm_chengpin_ip_status(vm_name):
    """获取成品虚拟机IP状态"""
    return get_ip_status_generic(vm_name, '成品虚拟机', VM_DIRS['chengpin'])

@app.route('/api/vm_chengpin_execute_script', methods=['POST'])
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
        
        logger.info(f"处理后的结果: success={success}, output_length={len(output) if output else 0}, error={error}, log_length={len(full_log) if full_log else 0}")
        
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

@app.route('/api/vm_chengpin_execute_scripts', methods=['POST'])
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

@app.route('/api/vm_10_12_list')
@login_required
def api_vm_10_12_list():
    """获取10.12目录虚拟机列表"""
    return get_vm_list_from_directory(VM_DIRS['10_12'], '10.12目录')

@app.route('/api/get_10_12_wuma_info', methods=['POST'])
@login_required
def api_get_10_12_wuma_info():
    """获取10.12目录虚拟机五码信息"""
    return get_wuma_info_generic('10.12目录')

@app.route('/api/get_10_12_ju_info', methods=['POST'])
@login_required
def api_get_10_12_ju_info():
    """获取10.12目录虚拟机JU值信息"""
    return get_ju_info_generic('10.12目录')

@app.route('/api/vm_10_12_online_status', methods=['POST'])
@login_required
def api_vm_10_12_online_status():
    """获取10.12目录虚拟机在线状态"""
    logger.info("收到获取10.12目录虚拟机在线状态请求")
    try:
        data = request.get_json()
        vm_names = data.get('vm_names', [])
        
        if not vm_names:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称列表'
            })
        
        results = {}
        for vm_name in vm_names:
            try:
                online_status = get_vm_online_status(vm_name)
                results[vm_name] = online_status
                print(f"[DEBUG] 10.12虚拟机 {vm_name} 在线状态结果: {online_status}")
            except Exception as e:
                logger.error(f"获取虚拟机 {vm_name} 在线状态失败: {str(e)}")
                print(f"[DEBUG] 10.12虚拟机 {vm_name} 获取状态失败: {str(e)}")
                results[vm_name] = {
                    'status': 'error',
                    'reason': f'获取状态失败: {str(e)}',
                    'ip': None,
                    'ssh_trust': False,
                    'ssh_port_open': False,
                    'vm_status': 'unknown'
                }
        
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        logger.error(f"获取10.12目录虚拟机在线状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取10.12目录虚拟机在线状态失败: {str(e)}'
        })

@app.route('/api/ssh_10_12_trust', methods=['POST'])
@login_required
def api_ssh_10_12_trust():
    """设置10.12目录虚拟机SSH互信"""
    logger.info("收到设置10.12目录虚拟机SSH互信请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        username = data.get('username', vm_username)
        password = data.get('password', '123456')
        
        if not vm_name:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称参数'
            })
        
        # 获取虚拟机IP
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            return jsonify({
                'success': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址'
            })
        
        # 设置SSH互信
        success, message = setup_ssh_trust(vm_ip, username, password)
        
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        logger.error(f"设置10.12目录虚拟机SSH互信失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'设置10.12目录虚拟机SSH互信失败: {str(e)}'
        })

@app.route('/api/vm_10_12_delete', methods=['POST'])
@login_required
def api_vm_10_12_delete():
    """删除10.12目录虚拟机"""
    return delete_vm_generic('10.12目录', VM_DIRS['10_12'])

@app.route('/api/vm_10_12_start', methods=['POST'])
@login_required
def api_vm_10_12_start():
    """启动10.12目录虚拟机"""
    return vm_operation_generic('start', '10.12目录', VM_DIRS['10_12'])

@app.route('/api/vm_10_12_stop', methods=['POST'])
@login_required
def api_vm_10_12_stop():
    """停止10.12目录虚拟机"""
    return vm_operation_generic('stop', '10.12目录', VM_DIRS['10_12'])

@app.route('/api/vm_10_12_restart', methods=['POST'])
@login_required
def api_vm_10_12_restart():
    """重启10.12目录虚拟机"""
    return vm_operation_generic('restart', '10.12目录', VM_DIRS['10_12'])

@app.route('/api/vm_10_12_info/<vm_name>')
@login_required
def api_vm_10_12_info(vm_name):
    """获取10.12目录虚拟机详细信息"""
    return get_vm_info_generic(vm_name, '10.12目录', VM_DIRS['10_12'])

@app.route('/api/vm_10_12_send_script', methods=['POST'])
@login_required
def api_vm_10_12_send_script():
    """向10.12目录虚拟机发送脚本"""
    return send_script_generic('10.12目录')

@app.route('/api/vm_10_12_add_permissions', methods=['POST'])
@login_required
def api_vm_10_12_add_permissions():
    """为10.12目录虚拟机添加脚本执行权限"""
    return add_permissions_generic('10.12目录')

@app.route('/api/vm_10_12_chmod_scripts', methods=['POST'])
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

@app.route('/api/vm_10_12_ip_status/<vm_name>')
@login_required
def api_vm_10_12_ip_status(vm_name):
    """获取10.12目录虚拟机IP状态"""
    return get_ip_status_generic(vm_name, '10.12目录', VM_DIRS['10_12'])

@app.route('/api/vm_10_12_execute_script', methods=['POST'])
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
        logger.info(f"开始执行脚本 {script_name} 在虚拟机 {vm_name} ({vm_info['ip']})")
        result = execute_remote_script(vm_info['ip'], 'wx', script_name)
        
        logger.info(f"execute_remote_script 返回结果: {result}")
        
        if len(result) == 3:
            success, output, full_log = result
            error = ""
        elif len(result) == 4:
            success, output, error, full_log = result
        else:
            success, output, error, full_log = False, "", "未知错误", ""
        
        logger.info(f"处理后的结果: success={success}, output_length={len(output) if output else 0}, error={error}, log_length={len(full_log) if full_log else 0}")
        
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

@app.route('/api/vm_10_12_execute_scripts', methods=['POST'])
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

# 五码管理相关API路由
@app.route('/api/wuma_list')
@login_required
def api_wuma_list():
    """获取五码列表"""
    logger.info("收到获取五码列表请求")
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 5))
        config_name = request.args.get('config', 'config')  # 默认使用config.txt
        list_type = request.args.get('type', 'available')  # available 或 used
        
        logger.debug(f"请求参数 - page: {page}, page_size: {page_size}, config: {config_name}, type: {list_type}")
        
        # 根据类型选择配置文件路径
        if list_type == 'used':
            # 从 config_install 目录读取已使用的五码（加_install.bak后缀）
            config_file_path = os.path.join(wuma_config_install_dir, f'{config_name}_install.bak')
        elif list_type == 'deleted':
            # 从 config_del 目录读取已删除的五码（加_del.bak后缀）
            config_file_path = os.path.join(wuma_config_delete_dir, f'{config_name}_del.bak')
        else:
            # 从 config 目录读取可用的五码
            config_file_path = os.path.join(wuma_config_dir, f'{config_name}.txt')
        
        logger.debug(f"配置文件路径: {config_file_path}")
        
        wuma_data = []
        
        if os.path.exists(config_file_path):
            logger.debug(f"配置文件存在，开始读取")
            with open(config_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                logger.debug(f"读取到 {len(lines)} 行数据")
                
                for i, line in enumerate(lines, 1):
                    line = line.strip()
                    if line and line.startswith(':') and line.endswith(':'):  # 检查格式
                        # 去掉开头和结尾的冒号，然后按冒号分割数据
                        content = line[1:-1]  # 去掉首尾的冒号
                        parts = content.split(':')
                        if len(parts) >= 5:
                            wuma_item = {
                                'id': str(i),
                                'rom': parts[0],
                                'mlb': parts[1],
                                'serial_number': parts[2],
                                'board_id': parts[3],
                                'model_identifier': parts[4],
                                'status': 'used' if list_type == 'used' else 'valid'
                            }
                            wuma_data.append(wuma_item)
                            logger.debug(f"解析第 {i} 行数据: {wuma_item}")
                        else:
                            logger.warning(f"第 {i} 行数据格式不正确，跳过: {line}")
                    else:
                        logger.debug(f"第 {i} 行不是有效数据，跳过: {line}")
        else:
            logger.warning(f"配置文件不存在: {config_file_path}")
        
        logger.debug(f"总共解析到 {len(wuma_data)} 条有效数据")
        
        # 计算分页
        total_count = len(wuma_data)
        total_pages = (total_count + page_size - 1) // page_size
        start_index = (page - 1) * page_size
        end_index = min(start_index + page_size, total_count)
        
        logger.debug(f"分页信息 - 总数: {total_count}, 总页数: {total_pages}, 当前页: {page}, 起始索引: {start_index}, 结束索引: {end_index}")
        
        # 获取当前页的数据
        current_page_data = wuma_data[start_index:end_index]
        logger.debug(f"当前页数据条数: {len(current_page_data)}")
        
        # 计算统计信息
        stats = {
            'total': total_count,
            'valid': len([w for w in wuma_data if w['status'] == 'valid']),
            'invalid': len([w for w in wuma_data if w['status'] == 'invalid']),
            'used': len([w for w in wuma_data if w['status'] == 'used'])
        }
        
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'total_count': total_count,
            'start_index': start_index,
            'end_index': end_index
        }
        
        logger.info(f"成功返回五码列表 - 总数: {total_count}, 当前页: {page}/{total_pages}, 类型: {list_type}")
        
        return jsonify({
            'success': True,
            'wuma_list': current_page_data,
            'pagination': pagination,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"获取五码列表失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'获取五码列表失败: {str(e)}'
        })

@app.route('/api/wuma_configs')
@login_required
def api_wuma_configs():
    """获取可用的配置文件列表"""
    logger.info("收到获取配置文件列表请求")
    try:
        configs = []
        config_dir = wuma_config_dir
        
        # 确保config目录存在
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
            logger.info("创建config目录")
        
        # 查找config目录下的所有.txt文件
        if os.path.exists(config_dir):
            for filename in os.listdir(config_dir):
                if filename.endswith('.txt'):
                    file_path = os.path.join(config_dir, filename)
                    
                    # 检查文件是否为合规的五码文本文件
                    if is_valid_wuma_file(file_path):
                        config_name = filename[:-4]  # 去掉.txt后缀
                        configs.append({
                            'name': config_name,
                            'display_name': filename  # 直接显示文件名
                        })
                        logger.info(f"发现合规的五码文件: {filename}")
                    else:
                        logger.warning(f"跳过不合规的文件: {filename}")
            
            # 按名称排序
            configs.sort(key=lambda x: x['name'])
            
            logger.info(f"找到 {len(configs)} 个合规的五码配置文件")
            
            return jsonify({
                'success': True,
                'configs': configs
            })
        
    except Exception as e:
        logger.error(f"获取配置文件列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取配置文件列表失败: {str(e)}'
        })

def is_valid_wuma_file(file_path):
    """检查文件是否为合规的五码文本文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            return False
        
        lines = content.split('\n')
        valid_lines = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查格式：:ROM:MLB:SN:BoardID:Model:
            if not (line.startswith(':') and line.endswith(':')):
                continue
            
            # 分割并检查字段数量
            parts = line.split(':')
            if len(parts) != 7:  # 包括首尾的空字符串
                continue
            
            # 检查中间5个字段是否不为空
            if any(not parts[i].strip() for i in range(1, 6)):
                continue
            
            valid_lines += 1
        
        # 文件至少包含1行有效数据才认为是合规的
        return valid_lines > 0
        
    except Exception as e:
        logger.error(f"检查文件合规性失败 {file_path}: {str(e)}")
        return False

@app.route('/api/wuma_upload', methods=['POST'])
@login_required
def api_wuma_upload():
    """上传五码文件"""
    logger.info("收到上传五码文件请求")
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': '没有选择文件'
            })
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': '没有选择文件'
            })
        
        # 检查文件类型
        if not file.filename.lower().endswith(('.txt', '.csv')):
            return jsonify({
                'success': False,
                'message': '文件类型不正确，请选择.txt或.csv文件'
            })
        
        # 获取自定义文件名
        custom_filename = request.form.get('custom_filename', '').strip()
        if custom_filename:
            # 清理文件名，移除特殊字符
            import re
            custom_filename = re.sub(r'[<>:"/\\|?*]', '', custom_filename)
            filename = f"{custom_filename}.txt"
        else:
            # 使用原文件名
            filename = file.filename
            if not filename.lower().endswith('.txt'):
                filename = filename.rsplit('.', 1)[0] + '.txt'
        
        # 确保config目录存在
        config_dir = wuma_config_dir
        os.makedirs(config_dir, exist_ok=True)
        
        # 构建文件路径
        file_path = os.path.join(config_dir, filename)
        
        # 读取文件内容进行校验
        content = file.read().decode('utf-8')
        lines = content.strip().split('\n')
        
        if not lines or all(line.strip() == '' for line in lines):
            return jsonify({
                'success': False,
                'message': '文件为空，请选择包含数据的文件'
            })
        
        # 校验文件格式
        valid_lines = []
        invalid_lines = 0
        errors = []
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            # 严格校验格式：:ROM:MLB:SN:BoardID:Model:
            if not (line.startswith(':') and line.endswith(':')):
                invalid_lines += 1
                errors.append(f"第{line_num}行格式错误：{line}")
                continue
            
            # 分割并检查字段数量
            parts = line.split(':')
            if len(parts) != 7:  # 包括首尾的空字符串
                invalid_lines += 1
                errors.append(f"第{line_num}行字段数量错误：{line}")
                continue
            
            # 检查中间5个字段是否为空
            if any(not parts[i].strip() for i in range(1, 6)):
                invalid_lines += 1
                errors.append(f"第{line_num}行包含空字段：{line}")
                continue
            
            valid_lines.append(line)
        
        if invalid_lines > 0:
            return jsonify({
                'success': False,
                'message': f'文件格式校验失败，发现{invalid_lines}行格式错误',
                'errors': errors[:5]  # 只返回前5个错误
            })
        
        # 保存文件到config目录
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(valid_lines))
            
            logger.info(f"成功保存 {len(valid_lines)} 条五码数据到 {filename}")
            
            return jsonify({
                'success': True,
                'message': f'上传成功！文件已保存到config目录，共{len(valid_lines)}条有效数据',
                'filename': filename,
                'valid_count': len(valid_lines)
            })
            
        except Exception as e:
            logger.error(f"保存文件失败: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'保存文件失败: {str(e)}'
            })
        
    except Exception as e:
        logger.error(f"上传五码文件失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'上传五码文件失败: {str(e)}'
        })



@app.route('/api/wuma_delete', methods=['POST'])
@login_required
def api_wuma_delete():
    """删除五码信息并保存到备份文件"""
    logger.info("收到删除五码信息请求")
    try:
        data = request.get_json()
        logger.info(f"删除请求数据: {data}")
        
        wuma_id = data.get('wuma_id')  # 行索引
        config_file = data.get('config_file', 'config.txt')
        
        logger.info(f"解析参数 - wuma_id: {wuma_id}, config_file: {config_file}")
        
        if wuma_id is None:
            return jsonify({
                'success': False,
                'message': '缺少五码行索引'
            })
        
        # 构建配置文件路径
        config_dir = wuma_config_dir
        
        # 如果config_file不包含.txt扩展名，则添加
        if not config_file.endswith('.txt'):
            config_file_path = os.path.join(config_dir, f'{config_file}.txt')
        else:
            config_file_path = os.path.join(config_dir, config_file)
        
        if not os.path.exists(config_file_path):
            return jsonify({
                'success': False,
                'message': f'配置文件 {config_file_path} 不存在'
            })
        
        # 读取原文件内容
        with open(config_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 移除空行和空白字符
        lines = [line.strip() for line in lines if line.strip()]
        
        # 检查行索引是否有效
        logger.info(f"原始wuma_id: {wuma_id}, 类型: {type(wuma_id)}")
        try:
            row_index = int(wuma_id)
            logger.info(f"转换后的row_index: {row_index}, 类型: {type(row_index)}")
            logger.info(f"文件总行数: {len(lines)}")
            
            if row_index < 0 or row_index >= len(lines):
                logger.warning(f"行索引 {row_index} 超出范围 (0-{len(lines)-1})")
                return jsonify({
                    'success': False,
                    'message': f'行索引 {row_index} 超出范围 (0-{len(lines)-1})'
                })
        except ValueError as e:
            logger.error(f"行索引转换失败: {e}, 原始值: {wuma_id}")
            return jsonify({
                'success': False,
                'message': f'无效的行索引: {wuma_id}'
            })
        
        # 获取要删除的行内容
        deleted_line = lines[row_index]
        
        # 删除指定行
        lines.pop(row_index)
        
        # 创建备份目录
        backup_dir = wuma_config_delete_dir
        os.makedirs(backup_dir, exist_ok=True)
        
        # 生成备份文件名：原文件名_del.bak
        backup_filename = f'{config_file}_del.bak'
        backup_file_path = os.path.join(backup_dir, backup_filename)
        
        # 追加到备份文件
        with open(backup_file_path, 'a', encoding='utf-8') as f:
            f.write(deleted_line + '\n')
        
        # 更新原文件
        with open(config_file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
        
        logger.info(f"成功删除第 {row_index} 行，内容: {deleted_line}")
        logger.info(f"备份文件保存到: {backup_file_path}")
        logger.info(f"原文件剩余 {len(lines)} 行")
        
        return jsonify({
            'success': True,
            'message': f'删除成功！已删除第 {row_index + 1} 行，备份文件: {backup_filename}',
            'deleted_line': deleted_line,
            'backup_file': backup_filename,
            'remaining_lines': len(lines),
            'row_index': row_index
        })
        
    except Exception as e:
        logger.error(f"删除五码信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除五码信息失败: {str(e)}'
        })

@app.route('/api/batch_change_wuma', methods=['POST'])
@login_required
def api_batch_change_wuma():
    """批量更改五码API"""
    logger.info("收到批量更改五码API请求")
    try:
        data = request.get_json()
        logger.info(f"批量更改五码请求数据: {data}")
        
        default_config = data.get('default_config', 'config.txt')
        selected_vms = data.get('selected_vms', [])
        logger.info(f"使用配置文件: {default_config}")
        logger.info(f"选中的虚拟机: {selected_vms}")
        
        if not selected_vms:
            return jsonify({
                'success': False,
                'message': '没有选中任何虚拟机'
            })
        
        # 构建配置文件路径
        config_dir = wuma_config_dir
        if not default_config.endswith('.txt'):
            config_file_path = os.path.join(config_dir, f'{default_config}.txt')
        else:
            config_file_path = os.path.join(config_dir, default_config)
        
        if not os.path.exists(config_file_path):
            return jsonify({
                'success': False,
                'message': f'配置文件 {config_file_path} 不存在'
            })
        
        # 读取五码配置文件
        with open(config_file_path, 'r', encoding='utf-8') as f:
            wuma_lines = f.readlines()
        
        # 过滤有效行
        valid_wuma_lines = [line.strip() for line in wuma_lines if line.strip() and is_valid_wuma_file_line(line.strip())]
        
        if not valid_wuma_lines:
            return jsonify({
                'success': False,
                'message': '配置文件中没有有效的五码数据'
            })
        
        # 检查五码数据是否足够
        if len(valid_wuma_lines) < len(selected_vms):
            return jsonify({
                'success': False,
                'message': f'五码数据不足，需要 {len(selected_vms)} 个，但只有 {len(valid_wuma_lines)} 个'
            })
        
        # 验证选中的虚拟机是否都在运行
        vmrun_path = get_vmrun_path()
        
        list_cmd = [vmrun_path, 'list']
        logger.debug(f"执行vmrun命令: {list_cmd}")
        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return jsonify({
                'success': False,
                'message': f'获取运行中虚拟机列表失败: {result.stderr}'
            })
        
        running_vms = result.stdout.strip().split('\n')[1:]  # 跳过标题行
        logger.info(f"获取到运行中虚拟机: {running_vms}")
        logger.info(f"选中的虚拟机: {selected_vms}")
        
        # 验证选中的虚拟机是否都在运行
        for vm_name in selected_vms:
            # 检查虚拟机名称是否在运行列表中（支持完整路径匹配）
            vm_running = False
            for running_vm in running_vms:
                # 检查完整路径或文件名是否匹配
                if vm_name in running_vm or running_vm.endswith(vm_name):
                    vm_running = True
                    break
            
            if not vm_running:
                logger.warning(f"虚拟机 {vm_name} 不在运行状态，运行中虚拟机列表: {running_vms}")
                return jsonify({
                    'success': False,
                    'message': f'虚拟机 {vm_name} 不在运行状态'
                })
        
        # 读取temp.plist模板
        plist_template_path = os.path.join(plist_template_dir, 'temp.plist')
        logger.info(f"检查temp.plist模板文件: {plist_template_path}")
        if not os.path.exists(plist_template_path):
            logger.error(f"temp.plist模板文件不存在: {plist_template_path}")
            return jsonify({
                'success': False,
                'message': f'temp.plist模板文件不存在: {plist_template_path}'
            })
        
        logger.info(f"temp.plist模板文件存在，开始读取...")
        with open(plist_template_path, 'r', encoding='utf-8') as f:
            plist_template = f.read()
        logger.info(f"temp.plist模板读取完成，长度: {len(plist_template)}")
        
        # 创建备份目录
        backup_dir = wuma_config_install_dir
        logger.info(f"创建备份目录: {backup_dir}")
        os.makedirs(backup_dir, exist_ok=True)
        
        results = []
        used_wuma_lines = []
        
        # 为每个选中的虚拟机生成plist文件
        for i, vm_name in enumerate(selected_vms):
            if i >= len(valid_wuma_lines):
                logger.warning(f"五码数据不足，跳过虚拟机: {vm_name}")
                results.append({
                    'vm_name': vm_name,
                    'success': False,
                    'message': '五码数据不足'
                })
                continue
            
            # 找到对应的运行中虚拟机路径
            vm_path = None
            for running_vm in running_vms:
                if vm_name in running_vm or running_vm.endswith(vm_name):
                    vm_path = running_vm
                    logger.info(f"找到虚拟机 {vm_name} 的运行路径: {vm_path}")
                    break
            
            if not vm_path:
                logger.error(f"未找到虚拟机 {vm_name} 的运行路径，运行中虚拟机列表: {running_vms}")
                results.append({
                    'vm_name': vm_name,
                    'success': False,
                    'message': '未找到虚拟机运行路径'
                })
                continue
            
            try:
                # 解析五码数据
                wuma_line = valid_wuma_lines[i]
                wuma_parts = wuma_line.split(':')
                if len(wuma_parts) != 7:
                    logger.error(f"五码格式错误: {wuma_line}")
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': f'五码格式错误: {wuma_line}'
                    })
                    continue
                
                # 提取五码字段
                rom = wuma_parts[1]
                mlb = wuma_parts[2]
                serial_number = wuma_parts[3]
                board_id = wuma_parts[4]
                model = wuma_parts[5]
                
                # 生成UUID
                custom_uuid = str(uuid.uuid4()).upper()
                sm_uuid = str(uuid.uuid4()).upper()
                
                # 对ROM进行PowerShell风格的base64加密
                try:
                    # 检查ROM是否为有效的十六进制字符串
                    if not all(c in '0123456789ABCDEFabcdef' for c in rom):
                        logger.warning(f"ROM值 {rom} 包含非十六进制字符，使用UTF-8编码")
                        rom_bytes = rom.encode('utf-8')
                    else:
                        # 模拟PowerShell逻辑：按每2个字符分割，转换为字节
                        rom_pairs = [rom[i:i+2] for i in range(0, len(rom), 2)]
                        rom_bytes = bytes([int(pair, 16) for pair in rom_pairs])
                    
                    rom_base64 = base64.b64encode(rom_bytes).decode('utf-8')
                    rom_formatted = rom_base64  # 格式化为 ROM :base64结果
                    logger.info(f"ROM原始值: {rom}, PowerShell风格字节: {rom_bytes}, base64加密后: {rom_base64}, 格式化后: {rom_formatted}")
                except ValueError as e:
                    logger.error(f"ROM PowerShell风格转换失败: {e}, 使用UTF-8编码")
                    rom_bytes = rom.encode('utf-8')
                    rom_base64 = base64.b64encode(rom_bytes).decode('utf-8')
                    rom_formatted = rom_base64
                    logger.info(f"ROM原始值: {rom}, UTF-8编码后: {rom_bytes}, base64加密后: {rom_base64}, 格式化后: {rom_formatted}")
                
                # 替换plist模板中的占位符
                plist_content = plist_template
                plist_content = plist_content.replace('$1', model)
                plist_content = plist_content.replace('$2', board_id)
                plist_content = plist_content.replace('$3', serial_number)
                plist_content = plist_content.replace('$4', custom_uuid)
                plist_content = plist_content.replace('$5', rom_formatted)  # 使用格式化后的ROM
                plist_content = plist_content.replace('$6', mlb)
                plist_content = plist_content.replace('$7', sm_uuid)
                
                # 生成plist文件
                plist_filename = f"{vm_name}.plist"
                plist_file_path = os.path.join(os.path.dirname(__file__), 'config', 'chengpin_plist', plist_filename)
                os.makedirs(os.path.dirname(plist_file_path), exist_ok=True)
                
                with open(plist_file_path, 'w', encoding='utf-8') as f:
                    f.write(plist_content)
                
                logger.info(f"生成plist文件: {plist_file_path}")
                
                # 获取虚拟机IP
                vm_ip = get_vm_ip(vm_name)
                logger.info(f"获取虚拟机 {vm_name} 的IP: {vm_ip}")
                if not vm_ip:
                    logger.error(f"无法获取虚拟机 {vm_name} 的IP")
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': '无法获取虚拟机IP'
                    })
                    continue
                
                # 执行mount_efi.sh脚本
                mount_cmd = f'ssh {vm_username}@{vm_ip} "~/mount_efi.sh"'
                logger.info(f"执行mount命令: {mount_cmd}")
                mount_result = subprocess.run(mount_cmd, shell=True, capture_output=True, text=True, timeout=60)
                
                if mount_result.returncode != 0:
                    logger.warning(f"mount_efi.sh执行失败: {mount_result.stderr}")
                    # 继续执行，不中断流程
                else:
                    logger.info(f"mount_efi.sh执行成功")
                
                # 传输plist文件到虚拟机
                scp_cmd = f'scp "{plist_file_path}" {vm_username}@{vm_ip}:{boot_config_path}'
                logger.info(f"执行scp命令: {scp_cmd}")
                scp_result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True, timeout=60)
                
                if scp_result.returncode != 0:
                    logger.error(f"文件传输失败: {scp_result.stderr}")
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': f'文件传输失败: {scp_result.stderr}'
                    })
                    continue
                else:
                    logger.info(f"文件传输成功")
                
                # 备份已使用的五码到同名配置文件加_install.bak后缀
                backup_config_file = os.path.join(backup_dir, f'{default_config}_install.bak')
                if not default_config.endswith('.txt'):
                    backup_config_file = os.path.join(backup_dir, f'{default_config}_install.bak')
                
                # 追加到备份配置文件
                with open(backup_config_file, 'a', encoding='utf-8') as f:
                    f.write(wuma_line + '\n')
                
                used_wuma_lines.append(wuma_line)
                
                # 重启虚拟机
                logger.info(f"开始重启虚拟机 {vm_name}")
                restart_cmd = [vmrun_path, 'stop', vm_path]
                logger.info(f"停止虚拟机: {restart_cmd}")
                stop_result = subprocess.run(restart_cmd, capture_output=True, timeout=30)
                
                if stop_result.returncode != 0:
                    logger.warning(f"停止虚拟机失败: {stop_result.stderr}")
                else:
                    logger.info(f"虚拟机停止成功")
                
                time.sleep(5)  # 等待虚拟机完全停止
                
                restart_cmd = [vmrun_path, 'start', vm_path, 'nogui']
                logger.info(f"启动虚拟机: {restart_cmd}")
                start_result = subprocess.run(restart_cmd, capture_output=True, timeout=30)
                
                if start_result.returncode != 0:
                    logger.warning(f"启动虚拟机失败: {start_result.stderr}")
                else:
                    logger.info(f"虚拟机启动成功")
                
                results.append({
                    'vm_name': vm_name,
                    'success': True,
                    'message': '批量更改五码成功'
                })
                
                logger.info(f"虚拟机 {vm_name} 批量更改五码完成")
                
            except Exception as e:
                logger.error(f"处理虚拟机 {vm_name} 时出错: {str(e)}")
                results.append({
                    'vm_name': vm_name,
                    'success': False,
                    'message': f'处理失败: {str(e)}'
                })
        
        # 从原配置文件中移除已使用的五码
        remaining_lines = [line.strip() for line in wuma_lines if line.strip() and line.strip() not in used_wuma_lines]
        
        with open(config_file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(remaining_lines) + '\n')
        
        logger.info(f"已从原配置文件移除 {len(used_wuma_lines)} 个已使用的五码，剩余 {len(remaining_lines)} 个")
        
        success_count = sum(1 for r in results if r['success'])
        total_count = len(results)
        
        logger.info(f"批量更改五码完成 - 成功: {success_count}/{total_count}")
        
        return jsonify({
            'success': True,
            'message': f'批量更改五码完成！成功处理 {success_count}/{total_count} 个虚拟机',
            'results': results
        })
        
    except Exception as e:
        logger.error(f"批量更改五码失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量更改五码失败: {str(e)}'
        })

@app.route('/api/batch_change_ju', methods=['POST'])
@login_required
def api_batch_change_ju():
    """批量更改JU值"""
    logger.info("收到批量更改JU值请求")
    try:
        data = request.get_json()
        logger.info(f"批量更改JU值请求数据: {data}")
        
        selected_vms = data.get('selected_vms', [])
        
        if not selected_vms:
            return jsonify({
                'success': False,
                'message': '未选择虚拟机'
            })
        
        logger.info(f"选中的虚拟机: {selected_vms}")
        
        # 创建任务ID
        task_id = f"batch_change_ju_{int(time.time())}"
        tasks[task_id] = {
            'status': 'running',
            'progress': 0,
            'total': len(selected_vms),
            'current': 0,
            'results': [],
            'logs': []
        }
        
        # 启动后台任务
        import threading
        thread = threading.Thread(target=batch_change_ju_worker, args=(task_id, selected_vms))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '批量更改JU值任务已启动'
        })
        
    except Exception as e:
        logger.error(f"批量更改JU值请求处理失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'请求处理失败: {str(e)}'
        })


def batch_change_ju_worker(task_id, selected_vms):
    """批量更改JU值后台工作函数"""
    logger.info(f"开始批量更改JU值任务: {task_id}")
    
    try:
        # 验证选中的虚拟机是否都在运行
        vmrun_path = get_vmrun_path()
        
        list_cmd = [vmrun_path, 'list']
        logger.debug(f"执行vmrun命令: {list_cmd}")
        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            add_task_log(task_id, 'ERROR', f'获取运行中虚拟机列表失败: {result.stderr}')
            tasks[task_id]['status'] = 'failed'
            return
        
        running_vms = result.stdout.strip().split('\n')[1:]  # 跳过标题行
        logger.info(f"获取到运行中虚拟机: {running_vms}")
        
        # 验证选中的虚拟机是否都在运行
        for vm_name in selected_vms:
            vm_running = False
            for running_vm in running_vms:
                if vm_name in running_vm or running_vm.endswith(vm_name):
                    vm_running = True
                    break
            
            if not vm_running:
                add_task_log(task_id, 'ERROR', f'虚拟机 {vm_name} 不在运行状态')
                tasks[task_id]['status'] = 'failed'
                return
        
        # 为每个选中的虚拟机执行JU值更改
        for i, vm_name in enumerate(selected_vms):
            try:
                add_task_log(task_id, 'INFO', f'开始处理虚拟机: {vm_name}')
                
                # 找到对应的运行中虚拟机路径
                vm_path = None
                for running_vm in running_vms:
                    if vm_name in running_vm or running_vm.endswith(vm_name):
                        vm_path = running_vm
                        logger.info(f"找到虚拟机 {vm_name} 的运行路径: {vm_path}")
                        break
                
                if not vm_path:
                    logger.error(f"未找到虚拟机 {vm_name} 的运行路径")
                    add_task_log(task_id, 'ERROR', f'未找到虚拟机 {vm_name} 的运行路径')
                    tasks[task_id]['results'].append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': '未找到虚拟机运行路径'
                    })
                    continue
                
                # 获取虚拟机IP
                vm_ip = get_vm_ip(vm_name)
                if not vm_ip:
                    add_task_log(task_id, 'ERROR', f'无法获取虚拟机 {vm_name} 的IP')
                    tasks[task_id]['results'].append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': '无法获取虚拟机IP'
                    })
                    continue
                
                add_task_log(task_id, 'INFO', f'虚拟机 {vm_name} IP: {vm_ip}')
                
                # 执行test.sh脚本
                test_cmd = f'ssh -o StrictHostKeyChecking=no wx@{vm_ip} "~/test.sh"'
                logger.info(f"执行test.sh脚本: {test_cmd}")
                add_task_log(task_id, 'INFO', f'执行test.sh脚本: {vm_name}')
                test_result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=60)
                
                if test_result.returncode != 0:
                    add_task_log(task_id, 'ERROR', f'test.sh脚本执行失败: {test_result.stderr}')
                    tasks[task_id]['results'].append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': f'test.sh脚本执行失败: {test_result.stderr}'
                    })
                    continue
                
                add_task_log(task_id, 'INFO', f'test.sh脚本执行成功: {vm_name}')
                
                # 重启虚拟机
                add_task_log(task_id, 'INFO', f'开始重启虚拟机: {vm_name}')
                restart_cmd = [vmrun_path, 'stop', vm_path]
                logger.info(f"停止虚拟机: {restart_cmd}")
                subprocess.run(restart_cmd, capture_output=True, timeout=30)
                
                time.sleep(5)  # 等待虚拟机完全停止
                
                restart_cmd = [vmrun_path, 'start', vm_path, 'nogui'] 
                logger.info(f"启动虚拟机: {restart_cmd}")
                subprocess.run(restart_cmd, capture_output=True, timeout=30)
                
                add_task_log(task_id, 'INFO', f'虚拟机 {vm_name} 重启完成')
                
                tasks[task_id]['results'].append({
                    'vm_name': vm_name,
                    'success': True,
                    'message': '脚本执行完毕，虚拟机正在重启中'
                })
                
                logger.info(f"虚拟机 {vm_name} 批量更改JU值完成")
                
                # 更新进度
                tasks[task_id]['current'] = i + 1
                tasks[task_id]['progress'] = int((i + 1) / len(selected_vms) * 100)
                
            except Exception as e:
                logger.error(f"处理虚拟机 {vm_name} 时出错: {str(e)}")
                add_task_log(task_id, 'ERROR', f'处理虚拟机 {vm_name} 时出错: {str(e)}')
                tasks[task_id]['results'].append({
                    'vm_name': vm_name,
                    'success': False,
                    'message': f'处理失败: {str(e)}'
                })
        
        success_count = sum(1 for r in tasks[task_id]['results'] if r['success'])
        total_count = len(tasks[task_id]['results'])
        
        add_task_log(task_id, 'INFO', f'批量更改JU值完成 - 成功: {success_count}/{total_count}')
        logger.info(f"批量更改JU值完成 - 成功: {success_count}/{total_count}")
        
        tasks[task_id]['status'] = 'completed'
        
    except Exception as e:
        logger.error(f"批量更改JU值任务失败: {str(e)}")
        add_task_log(task_id, 'ERROR', f'批量更改JU值任务失败: {str(e)}')
        tasks[task_id]['status'] = 'failed'


@app.route('/api/batch_change_ju_status/<task_id>')
@login_required
def api_batch_change_ju_status(task_id):
    """获取批量更改JU值任务状态"""
    if task_id not in tasks:
        return jsonify({
            'success': False,
            'message': '任务不存在'
        })
    
    task = tasks[task_id]
    return jsonify({
        'success': True,
        'status': task['status'],
        'progress': task['progress'],
        'current': task['current'],
        'total': task['total'],
        'results': task['results'],
        'logs': task['logs']
    })

@app.route('/api/batch_delete_vm', methods=['POST'])
@login_required
def api_batch_delete_vm():
    """批量删除虚拟机"""
    logger.info("收到批量删除虚拟机请求")
    try:
        data = request.get_json()
        logger.info(f"批量删除虚拟机请求数据: {data}")
        
        selected_vms = data.get('selected_vms', [])
        
        if not selected_vms:
            return jsonify({
                'success': False,
                'message': '未选择虚拟机'
            })
        
        logger.info(f"选中的虚拟机: {selected_vms}")
        
        # 验证选中的虚拟机是否都已停止
        vmrun_path = get_vmrun_path()
        
        list_cmd = [vmrun_path, 'list']
        logger.debug(f"执行vmrun命令: {list_cmd}")
        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return jsonify({
                'success': False,
                'message': f'获取运行中虚拟机列表失败: {result.stderr}'
            })
        
        running_vms = result.stdout.strip().split('\n')[1:]  # 跳过标题行
        logger.info(f"获取到运行中虚拟机: {running_vms}")
        
        # 验证选中的虚拟机是否都已停止
        for vm_name in selected_vms:
            vm_running = False
            for running_vm in running_vms:
                if vm_name in running_vm or running_vm.endswith(vm_name):
                    vm_running = True
                    break
            
            if vm_running:
                logger.warning(f"虚拟机 {vm_name} 仍在运行状态，无法删除")
                return jsonify({
                    'success': False,
                    'message': f'虚拟机 {vm_name} 仍在运行状态，请先停止虚拟机'
                })
        
        results = []
        
        # 为每个选中的虚拟机执行删除操作
        for vm_name in selected_vms:
            try:
                # 查找虚拟机文件
                vm_file = find_vm_file(vm_name)
                if not vm_file:
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': '未找到虚拟机文件'
                    })
                    continue
                
                # 删除虚拟机
                delete_cmd = [vmrun_path, 'deleteVM', vm_file]
                logger.info(f"删除虚拟机: {delete_cmd}")
                delete_result = subprocess.run(delete_cmd, capture_output=True, text=True, timeout=60)
                
                if delete_result.returncode != 0:
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': f'删除失败: {delete_result.stderr}'
                    })
                    continue
                
                results.append({
                    'vm_name': vm_name,
                    'success': True,
                    'message': '删除成功'
                })
                
                logger.info(f"虚拟机 {vm_name} 删除完成")
                
            except Exception as e:
                logger.error(f"处理虚拟机 {vm_name} 时出错: {str(e)}")
                results.append({
                    'vm_name': vm_name,
                    'success': False,
                    'message': f'处理失败: {str(e)}'
                })
        
        success_count = sum(1 for r in results if r['success'])
        total_count = len(results)
        
        logger.info(f"批量删除虚拟机完成 - 成功: {success_count}/{total_count}")
        
        return jsonify({
            'success': True,
            'message': f'批量删除虚拟机完成，成功: {success_count}/{total_count}',
            'results': results
        })
        
    except Exception as e:
        logger.error(f"批量删除虚拟机失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'批量删除虚拟机失败: {str(e)}'
        })

def is_valid_wuma_file_line(line):
    """验证五码文件行格式"""
    if not line.startswith(':') or not line.endswith(':'):
        return False
    
    parts = line.split(':')
    if len(parts) != 7:
        return False
    
    # 检查中间5个字段是否不为空
    for i in range(1, 6):
        if not parts[i].strip():
            return False
    
    return True

def count_available_wuma(file_path):
    """计算文件中可用的五码数量"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            return 0
        
        lines = content.split('\n')
        valid_count = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查格式：:ROM:MLB:SN:BoardID:Model:
            if not (line.startswith(':') and line.endswith(':')):
                continue
            
            # 分割并检查字段数量
            parts = line.split(':')
            if len(parts) != 7:  # 包括首尾的空字符串
                continue
            
            # 检查中间5个字段是否不为空
            if any(not parts[i].strip() for i in range(1, 6)):
                continue
            
            valid_count += 1
        
        return valid_count
        
    except Exception as e:
        logger.error(f"计算可用五码数量失败 {file_path}: {str(e)}")
        return 0

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)