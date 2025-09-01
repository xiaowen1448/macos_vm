import json
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from flask_socketio import SocketIO, emit
from functools import wraps
import os
from datetime import datetime, timedelta
import uuid
import threading
import time
import subprocess
import paramiko
import base64
import sys
import socket

from config import *

# 配置日志
from config import logs_dir

# 使用配置文件中的日志目录
log_dir = os.path.join(os.path.dirname(__file__), logs_dir)
os.makedirs(log_dir, exist_ok=True)

# 生成带日期的日志文件名
current_date = datetime.now().strftime('%Y-%m-%d')
app_log_file = os.path.join(log_dir, f'app_debug_{current_date}.log')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler(app_log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='web/templates', static_folder='web/static', static_url_path='/static')
import secrets
app.secret_key = secrets.token_hex(32)  # 生成随机session密钥
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)  # 设置session过期时间

# 初始化SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 设置Flask应用的日志级别
app.logger.setLevel(logging.DEBUG)

# 注册蓝图
from app.routes.mass_messaging import mass_messaging_bp
app.register_blueprint(mass_messaging_bp)

# 启动时清除所有session，确保每次启动都使用新的session
def clear_sessions_on_startup():
    """启动时清除所有session"""
    try:
        # 清除session文件（如果使用文件session）
        session_dir = os.path.join(os.path.dirname(__file__), 'flask_session')
        if os.path.exists(session_dir):
            import shutil
            shutil.rmtree(session_dir)
            os.makedirs(session_dir, exist_ok=True)
            logger.info("已清除所有session文件")
    except Exception as e:
        logger.warning(f"清除session文件失败: {e}")
    
    logger.info("应用启动，所有session已重置")

# 在应用启动时执行
clear_sessions_on_startup()

# 添加请求日志中间件
@app.before_request
def log_request_info():
    logger.info(f"收到请求: {request.method} {request.url}")
    logger.debug(f"请求头: {dict(request.headers)}")
   # if request.method == 'POST':
     #   logger.debug(f"POST数据: {request.get_data(as_text=True)}")

@app.after_request
def log_response_info(response):
    logger.info(f"响应状态: {response.status_code}")
    return response

# 使用全局配置文件中的认证信息
# USERNAME and PASSWORD are imported from config.py

# 虚拟机目录配置 - 使用全局配置
from config import clone_dir
VM_DIRS = {
    '10_12': clone_dir,
    'chengpin': vm_chengpin_dir
}

# 模板虚拟机路径 - 使用全局配置
# template_dir is imported from config.py

# 全局任务存储
clone_tasks = {}
tasks = {}
websockify_processes = {}  # 存储websockify进程信息

# IP监控和SSH连通性检测函数
def ping_vm_ip(ip_address, timeout=3):
    """检测虚拟机IP是否存活"""
    try:
        if os.name == 'nt':  # Windows
            cmd = ['ping', '-n', '1', '-w', str(timeout * 1000), ip_address]
        else:  # Linux/Mac
            cmd = ['ping', '-c', '1', '-W', str(timeout), ip_address]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
        return result.returncode == 0
    except Exception as e:
        logger.debug(f"Ping {ip_address} 失败: {str(e)}")
        return False

def check_ssh_connectivity(ip_address, username, timeout=10):
    """检测SSH连通性"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # 尝试连接（使用密钥认证）
        ssh.connect(
            hostname=ip_address,
            username=username,
            timeout=timeout,
            look_for_keys=True,
            allow_agent=True
        )
        
        # 执行简单命令测试连接
        stdin, stdout, stderr = ssh.exec_command('echo "ssh_test"', timeout=5)
        output = stdout.read().decode().strip()
        
        ssh.close()
        return output == 'ssh_test'
    except Exception as e:
        logger.debug(f"SSH连接 {ip_address} 失败: {str(e)}")
        return False

def check_and_complete_task(task_id):
    """检查所有监控任务是否完成，如果完成则标记主任务为完成状态"""
    if task_id not in clone_tasks:
        return
        
    task = clone_tasks[task_id]
    if 'monitoring' not in task:
        return
        
    monitoring = task['monitoring']
    completed_vms = monitoring.get('completed_vms', 0)
    total_vms = monitoring.get('total_vms', 0)
    
    # 检查是否所有虚拟机都已完成监控
    if completed_vms >= total_vms:
        success_vms = monitoring.get('success_vms', 0)
        failed_vms = monitoring.get('failed_vms', 0)
        
        if failed_vms == 0:
            task['status'] = 'completed'
            add_task_log(task_id, 'success', f'所有虚拟机监控和配置完成！成功: {success_vms}, 失败: {failed_vms}')
            print(f"[DEBUG] 所有虚拟机监控和配置完成！成功: {success_vms}, 失败: {failed_vms}")
        else:
            task['status'] = 'completed_with_errors'
            add_task_log(task_id, 'warning', f'虚拟机监控和配置完成，但有错误。成功: {success_vms}, 失败: {failed_vms}')
            print(f"[DEBUG] 虚拟机监控和配置完成，但有错误。成功: {success_vms}, 失败: {failed_vms}")
        
        # 强制刷新，确保前端能立即收到更新
        import sys
        sys.stdout.flush()

def monitor_vm_and_configure(task_id, vm_name, vm_path, wuma_config_file, max_wait_time=300):
    """监控虚拟机IP和SSH状态，连通后自动配置五码"""
    start_time = time.time()
    add_task_log(task_id, 'info', f'开始监控虚拟机 {vm_name} 的网络状态...')
    
    def update_monitoring_progress(success=False, failed=False, restart_progress=None, wuma_progress=None):
        """更新监控进度"""
        if task_id in clone_tasks:
            task = clone_tasks[task_id]
            if 'monitoring' in task:
                if success:
                    task['monitoring']['success_vms'] += 1
                elif failed:
                    task['monitoring']['failed_vms'] += 1
                task['monitoring']['completed_vms'] += 1
                
                # 更新重启进度和五码进度
                if restart_progress:
                    task['monitoring']['restart_progress'] = restart_progress
                if wuma_progress:
                    task['monitoring']['wuma_progress'] = wuma_progress
                
                # 发送监控进度更新
                progress_data = {
                    'type': 'monitoring_progress',
                    'vm_name': vm_name,
                    'completed': task['monitoring']['completed_vms'],
                    'total': task['monitoring']['total_vms'],
                    'success': task['monitoring']['success_vms'],
                    'failed': task['monitoring']['failed_vms']
                }
                
                # 添加重启进度和更改五码进度
                if 'restart_progress' in task['monitoring']:
                    progress_data['restart_progress'] = task['monitoring']['restart_progress']
                if 'wuma_progress' in task['monitoring']:
                    progress_data['wuma_progress'] = task['monitoring']['wuma_progress']
                    
                task['logs'].append(progress_data)
                print(f"[DEBUG] 发送监控进度更新: {progress_data}")
                
                # 强制刷新，确保前端能立即收到更新
                import sys
                sys.stdout.flush()
    
    try:
        while time.time() - start_time < max_wait_time:
            try:
                # 获取虚拟机IP（已集成强制重启逻辑）
                vm_ip = get_vm_ip(vm_name)
                if not vm_ip:
                    add_task_log(task_id, 'debug', f'虚拟机 {vm_name} IP获取失败，等待5秒后重试...')
                    time.sleep(5)
                    continue
                
                add_task_log(task_id, 'info', f'虚拟机 {vm_name} IP: {vm_ip}')
                
                # 检测IP存活
                if not ping_vm_ip(vm_ip):
                    add_task_log(task_id, 'debug', f'虚拟机 {vm_name} ({vm_ip}) ping不通，等待5秒后重试...')
                    time.sleep(5)
                    continue
                
                add_task_log(task_id, 'info', f'虚拟机 {vm_name} ({vm_ip}) ping通，检测SSH连通性...')
                
                # 检测SSH连通性
                if not check_ssh_connectivity(vm_ip, vm_username):
                    add_task_log(task_id, 'debug', f'虚拟机 {vm_name} ({vm_ip}) SSH未就绪，等待10秒后重试...')
                    time.sleep(10)
                    continue
                
                add_task_log(task_id, 'success', f'虚拟机 {vm_name} ({vm_ip}) SSH连通，开始配置五码...')
                
                # SSH连通后，执行五码配置和JU值更改流程
                try:
                    add_task_log(task_id, 'info', f'开始为虚拟机 {vm_name} 执行五码配置...')
                    print(f"[DEBUG] 开始为虚拟机 {vm_name} 执行五码配置，配置文件: {wuma_config_file}")
                    
                    result = batch_change_wuma_core([vm_name], wuma_config_file, task_id)
                    print(f"[DEBUG] 五码配置结果: {result}")
                    
                    if isinstance(result, dict) and result.get('status') == 'success':
                        add_task_log(task_id, 'success', f'虚拟机 {vm_name} 五码配置成功')
                        print(f"[DEBUG] 虚拟机 {vm_name} 五码配置成功")
                        
                        # 五码配置成功后，自动执行JU值更改
                        add_task_log(task_id, 'info', f'开始为虚拟机 {vm_name} 执行JU值更改...')
                        print(f"[DEBUG] 开始为虚拟机 {vm_name} 执行JU值更改")
                        
                        # 更新五码进度
                        if task_id in clone_tasks and 'monitoring' in clone_tasks[task_id]:
                            monitoring = clone_tasks[task_id]['monitoring']
                            # 使用线程安全的方式更新进度
                            monitoring['wuma_progress']['current'] = min(
                                monitoring['wuma_progress']['current'] + 1,
                                monitoring['wuma_progress']['total']
                            )
                            current_wuma = monitoring['wuma_progress']['current']
                            total_wuma = monitoring['wuma_progress']['total']
                            update_monitoring_progress(wuma_progress={'current': current_wuma, 'total': total_wuma})
                        
                        try:
                            # 执行test.sh脚本更改JU值
                            test_cmd = f'ssh -o StrictHostKeyChecking=no {vm_username}@{vm_ip} "{script_remote_path}/test.sh"'
                            print(f"[DEBUG] 执行JU值更改命令: {test_cmd}")
                            add_task_log(task_id, 'info', f'执行JU值更改脚本: {vm_name}')
                            
                            test_result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=60)
                            
                            if test_result.returncode == 0:
                                add_task_log(task_id, 'success', f'虚拟机 {vm_name} JU值更改成功')
                                print(f"[DEBUG] 虚拟机 {vm_name} JU值更改成功")
                                
                                # JU值更改成功后，重启虚拟机
                                add_task_log(task_id, 'info', f'开始重启虚拟机 {vm_name}...')
                                print(f"[DEBUG] 开始重启虚拟机 {vm_name}")
                                
                                # 更新重启进度
                                if task_id in clone_tasks and 'monitoring' in clone_tasks[task_id]:
                                    monitoring = clone_tasks[task_id]['monitoring']
                                    # 使用线程安全的方式更新进度
                                    monitoring['restart_progress']['current'] = min(
                                        monitoring['restart_progress']['current'] + 1,
                                        monitoring['restart_progress']['total']
                                    )
                                    current_restart = monitoring['restart_progress']['current']
                                    total_restart = monitoring['restart_progress']['total']
                                    update_monitoring_progress(restart_progress={'current': current_restart, 'total': total_restart})
                                
                                vmrun_path = get_vmrun_path()
                                
                                # 停止虚拟机
                                stop_cmd = [vmrun_path, 'stop', vm_path]
                                print(f"[DEBUG] 停止虚拟机命令: {' '.join(stop_cmd)}")
                                subprocess.run(stop_cmd, capture_output=True, timeout=30)
                                
                                time.sleep(5)  # 等待虚拟机完全停止
                                
                                # 启动虚拟机
                                start_cmd = [vmrun_path, 'start', vm_path, 'nogui']
                                print(f"[DEBUG] 启动虚拟机命令: {' '.join(start_cmd)}")
                                subprocess.run(start_cmd, capture_output=True, timeout=30)
                                
                                add_task_log(task_id, 'success', f'虚拟机 {vm_name} 重启完成，五码和JU值配置全部完成')
                                print(f"[DEBUG] 虚拟机 {vm_name} 重启完成，五码和JU值配置全部完成")
                                
                                update_monitoring_progress(success=True)
                                
                                # 检查是否所有虚拟机都已完成监控
                                check_and_complete_task(task_id)
                                return True
                            else:
                                add_task_log(task_id, 'error', f'虚拟机 {vm_name} JU值更改失败: {test_result.stderr}')
                                print(f"[DEBUG] 虚拟机 {vm_name} JU值更改失败: {test_result.stderr}")
                                update_monitoring_progress(failed=True)
                                
                                # 检查是否所有虚拟机都已完成监控
                                check_and_complete_task(task_id)
                                return False
                                
                        except Exception as ju_e:
                            add_task_log(task_id, 'error', f'虚拟机 {vm_name} JU值更改异常: {str(ju_e)}')
                            print(f"[DEBUG] 虚拟机 {vm_name} JU值更改异常: {str(ju_e)}")
                            update_monitoring_progress(failed=True)
                            
                            # 检查是否所有虚拟机都已完成监控
                            check_and_complete_task(task_id)
                            return False
                    else:
                        error_msg = result.get('message', '未知错误') if isinstance(result, dict) else '配置失败'
                        add_task_log(task_id, 'error', f'虚拟机 {vm_name} 五码配置失败: {error_msg}')
                        print(f"[DEBUG] 虚拟机 {vm_name} 五码配置失败: {error_msg}")
                        update_monitoring_progress(failed=True)
                        
                        # 检查是否所有虚拟机都已完成监控
                        check_and_complete_task(task_id)
                        return False
                except Exception as e:
                    error_detail = f'虚拟机 {vm_name} 五码配置异常: {str(e)}'
                    add_task_log(task_id, 'error', error_detail)
                    print(f"[DEBUG] {error_detail}")
                    print(f"[DEBUG] 异常详情: {type(e).__name__}: {str(e)}")
                    import traceback
                    print(f"[DEBUG] 异常堆栈: {traceback.format_exc()}")
                    update_monitoring_progress(failed=True)
                    
                    # 检查是否所有虚拟机都已完成监控
                    check_and_complete_task(task_id)
                    return False
                    
            except Exception as e:
                add_task_log(task_id, 'error', f'监控虚拟机 {vm_name} 时发生异常: {str(e)}')
                time.sleep(5)
        
        add_task_log(task_id, 'warning', f'虚拟机 {vm_name} 监控超时（{max_wait_time}秒），跳过五码配置')
        update_monitoring_progress(failed=True)
        
        # 检查是否所有虚拟机都已完成监控
        check_and_complete_task(task_id)
        return False
        
    except Exception as e:
        add_task_log(task_id, 'error', f'虚拟机 {vm_name} 监控线程异常: {str(e)}')
        update_monitoring_progress(failed=True)
        
        # 检查是否所有虚拟机都已完成监控
        check_and_complete_task(task_id)
        return False

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

# 通用函数 - 扫描脚本文件
def scan_scripts_from_directories():
    """从配置的多个目录扫描脚本文件"""
    scripts = []
    
    # 使用新的多目录配置
    for scripts_dir in script_upload_dirs:
        if os.path.exists(scripts_dir):
            logger.debug(f"扫描脚本目录: {scripts_dir}")
            for filename in os.listdir(scripts_dir):
                # 支持.sh和.scpt文件
                if filename.endswith('.sh') or filename.endswith('.scpt'):
                    file_path = os.path.join(scripts_dir, filename)
                    try:
                        # 获取文件信息
                        stat = os.stat(file_path)
                        size = stat.st_size
                        modified_time = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        
                        # 格式化文件大小
                        if size < 1024:
                            size_str = f"{size}B"
                        elif size < 1024 * 1024:
                            size_str = f"{size // 1024}KB"
                        else:
                            size_str = f"{size // (1024 * 1024)}MB"
                        
                        # 尝试读取脚本备注（从同名的.txt文件）
                        note_file = file_path.replace('.sh', '.txt').replace('.scpt', '.txt')
                        note = ""
                        if os.path.exists(note_file):
                            try:
                                with open(note_file, 'r', encoding='utf-8') as f:
                                    note = f.read().strip()
                            except Exception as e:
                                logger.warning(f"读取备注文件失败 {note_file}: {str(e)}")
                        
                        # 确定脚本类型
                        script_type = 'shell' if filename.endswith('.sh') else 'applescript'
                        
                        scripts.append({
                            'name': filename,
                            'size': size_str,
                            'modified_time': modified_time,
                            'path': file_path,
                            'note': note,
                            'type': script_type,
                            'directory': scripts_dir
                        })
                        
                        logger.debug(f"找到脚本文件: {filename}, 类型: {script_type}, 大小: {size_str}")
                        
                    except Exception as e:
                        logger.error(f"处理脚本文件 {filename} 时出错: {str(e)}")
                        continue
        else:
            logger.warning(f"脚本目录不存在: {scripts_dir}")
    
    # 按文件名排序
    scripts.sort(key=lambda x: x['name'])
    return scripts

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
        stats = {'total': 0, 'running': 0, 'stopped': 0, 'suspended': 0, 'online': 0}
        
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
                        
                        # 快速判断虚拟机状态（基于文件名匹配和挂起文件检查）
                        vm_status = 'stopped'
                        for running_vm in running_vms:
                            if vm_name in running_vm:
                                vm_status = 'running'
                                break
                        
                        # 如果不是运行状态，检查是否为挂起状态
                        if vm_status != 'running':
                            vm_dir_path = os.path.dirname(vm_path)
                            vmss_files = [f for f in os.listdir(vm_dir_path) if f.endswith('.vmss')]
                            if vmss_files:
                                vm_status = 'suspended'
                        
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
                        elif vm_status == 'suspended':
                            stats['suspended'] += 1
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
        
        logger.info(f"{vm_type_name}虚拟机列表获取完成 - 总数: {total_count}, 运行中: {stats['running']}, 已停止: {stats['stopped']}, 挂起: {stats['suspended']}")
        
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
        
        # 获取虚拟机IP（不执行强制重启）
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            return jsonify({
                'success': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址，请先启动虚拟机'
            })
        
        # 执行远程脚本获取五码信息
        result = execute_remote_script(vm_ip, 'wx', f'{script_remote_path}/run_debug_wuma.sh')
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
        
        # 获取虚拟机IP（不执行强制重启）
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            return jsonify({
                'success': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址，请先启动虚拟机'
            })
        
        # 执行远程脚本获取JU值信息
        result = execute_remote_script(vm_ip, 'wx', f'{script_remote_path}/run_debug_ju.sh')
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
        elif operation == 'suspend':
            cmd = [vmrun_path, 'suspend', vm_file]
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
        
        # 构建返回的虚拟机信息
        vm_info = {
            'name': vm_name,
            'path': vm_file,
            'status': vm_status,
            'snapshots': snapshots,
            'config': config
        }
        
        # 如果虚拟机处于挂起状态，获取挂起时间
        if vm_status == 'suspended':
            suspend_time = get_vm_suspend_time(vm_file)
            if suspend_time:
                vm_info['suspend_time'] = suspend_time
        
        return jsonify({
            'success': True,
            'vm_info': vm_info
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
        
        # 获取虚拟机IP（不执行强制重启）
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            return jsonify({
                'success': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址，请先启动虚拟机'
            })
        
        # 检查脚本文件是否存在（从配置的多个目录中查找）
        script_path = None
        for script_dir in script_upload_dirs:
            potential_path = os.path.join(script_dir, script_name)
            if os.path.exists(potential_path):
                script_path = potential_path
                break
        
        if not script_path:
            return jsonify({
                'success': False,
                'message': f'脚本文件 {script_name} 在配置的目录中不存在'
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
        
        # 获取虚拟机IP（不执行强制重启）
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            return jsonify({
                'success': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址，请先启动虚拟机'
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
            # 检查是否是AJAX请求
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Content-Type') == 'application/json':
                return jsonify({
                    'success': False,
                    'message': '请先登录',
                    'redirect': url_for('login')
                }), 401
            else:
                return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    logger.debug("登录页面访问")
    if request.method == 'POST':
        try:
            # 处理AJAX请求
            if request.headers.get('Content-Type') == 'application/json':
                data = request.get_json()
                username = data.get('username')
                password = data.get('password')
            else:
                # 处理表单请求
                username = request.form['username']
                password = request.form['password']
            
            logger.debug(f"用户尝试登录: {username}")
            if username == USERNAME and password == PASSWORD:
                session.permanent = True  # 设置session为永久性
                session['logged_in'] = True
                session['username'] = username
                session['login_time'] = datetime.now().isoformat()
                session['session_id'] = secrets.token_hex(16)  # 生成唯一session ID
                logger.info(f"用户 {username} 登录成功")
                
                # 返回JSON响应用于AJAX
                if request.headers.get('Content-Type') == 'application/json':
                    return jsonify({
                        'success': True,
                        'message': '登录成功',
                        'redirect': url_for('dashboard')
                    })
                else:
                    return redirect(url_for('dashboard'))
            else:
                logger.warning(f"用户 {username} 登录失败")
                error_msg = '用户名或密码错误'
                if request.headers.get('Content-Type') == 'application/json':
                    return jsonify({
                        'success': False,
                        'message': error_msg
                    })
                else:
                    flash(error_msg)
                    return render_template('login.html')
        except Exception as e:
            logger.error(f"登录处理异常: {e}")
            error_msg = '登录处理失败'
            if request.headers.get('Content-Type') == 'application/json':
                return jsonify({
                    'success': False,
                    'message': error_msg
                })
            else:
                flash(error_msg)
                return render_template('login.html')
    
    return render_template('login.html')
    
@app.route('/dashboard')
@login_required
def dashboard():
    logger.debug("访问dashboard页面")
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
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
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y/%m/%d %H:%M')
                size = stat.st_size
                script_list.append({'name': fname, 'mtime': mtime, 'size': size})
                logger.debug(f"找到脚本文件: {fname}, 大小: {size} bytes")
    script_list.sort(key=lambda x: x['name'])
    
    logger.info(f"Dashboard数据准备完成 - 成品VM: {len(vm_list)}, 临时VM: {len(vm_data)}, 脚本: {len(script_list)}")
    return render_template('dashboard.html', username=session.get('username'), vm_list=vm_list,vm_data=vm_data, script_list=script_list, wuma_list=wuma_list, current_time=current_time)

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
                            create_time = datetime.fromtimestamp(os.path.getmtime(vm_path))
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

@app.route('/id_management')
@login_required
def id_management_page():
    """ID管理页面"""
    return render_template('id_management.html')

@app.route('/test_mupan')
@login_required
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
                            create_time = datetime.fromtimestamp(os.path.getmtime(vm_path))
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

@app.route('/client_management')
@login_required
def client_management_page():
    """客户端管理页面"""
    return render_template('client_management.html')

@app.route('/json_parser')
@login_required
def json_parser_page():
    """JSON解析功能页面"""
    return render_template('json_parser.html')

@app.route('/phone_management')
@login_required
def phone_management_page():
    """手机号管理页面"""
    return render_template('phone_management.html')

# 批量发信相关路由已移动到 app/routes/mass_messaging.py

# 批量发信模板相关路由已移动到 app/routes/mass_messaging.py
    
# 批量发信核心API和其他相关路由已移动到 app/routes/mass_messaging.py

# websockify进程管理
websockify_processes = {}

@app.route('/api/vnc/connect', methods=['POST'])
@login_required
def api_vnc_connect():
    """VNC连接API - 使用websockify + noVNC方案"""
    try:
        data = request.get_json()
        client_ip = data.get('client_ip')
        
        if not client_ip:
            return jsonify({'success': False, 'message': '客户端IP不能为空'})
        
        logger.info(f"尝试为客户端IP {client_ip} 建立VNC连接")
        
        # 查找对应的VMX文件
        vmx_file = find_vmx_file_by_ip(client_ip)
        if not vmx_file:
            logger.warning(f"未找到客户端IP {client_ip} 对应的VMX文件")
            return jsonify({'success': False, 'message': f'未找到客户端IP {client_ip} 对应的虚拟机配置文件'})
        
        # 读取VNC配置
        vnc_config = read_vnc_config_from_vmx(vmx_file)
        if not vnc_config:
            logger.warning(f"VMX文件 {vmx_file} 中未找到VNC配置")
            return jsonify({'success': False, 'message': '虚拟机未启用VNC或配置不完整'})
        
        # 启动websockify进程
        websocket_port = start_websockify(client_ip, vnc_config['port'])
        if not websocket_port:
            return jsonify({'success': False, 'message': 'websockify启动失败'})
        
        logger.info(f"成功启动websockify: VNC端口={vnc_config['port']}, WebSocket端口={websocket_port}")
        
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

def find_vmx_file_by_ip(target_ip):
    """根据IP地址查找对应的VMX文件"""
    try:
        vmrun_path = get_vmrun_path()
        
        # 首先获取运行中的虚拟机列表
        list_cmd = [vmrun_path, 'list']
        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"获取运行中虚拟机列表失败: {result.stderr}")
            return None
        
        running_vms = []
        lines = result.stdout.strip().split('\n')
        
        # 解析vmrun list输出
        for line in lines[1:]:  # 跳过第一行（Total running VMs: X）
            line = line.strip()
            if line and os.path.exists(line) and line.endswith('.vmx'):
                running_vms.append(line)
        
        # 对每个运行中的虚拟机，检查其IP地址是否匹配
        for vm_path in running_vms:
            try:
                # 使用vmrun获取虚拟机IP
                command = f'"{vmrun_path}" getGuestIPAddress "{vm_path}"'
                ip_result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
                
                if ip_result.returncode == 0:
                    vm_ip = ip_result.stdout.strip()
                    # 如果IP匹配且有VNC配置，返回这个VMX文件
                    if vm_ip == target_ip and has_vnc_config(vm_path):
                        logger.info(f"找到匹配IP {target_ip} 的VMX文件: {vm_path}")
                        return vm_path
                        
            except Exception as e:
                logger.debug(f"检查虚拟机 {vm_path} 的IP时出错: {str(e)}")
                continue
        
        # 如果没有找到匹配的运行中虚拟机，尝试根据IP查找对应的VMX文件
        logger.warning(f"未找到运行中的虚拟机匹配IP {target_ip}，尝试根据IP查找对应的VMX文件")
        
        # 根据IP地址推断可能的虚拟机名称或目录
        # 搜索克隆目录中包含该IP信息的VMX文件
        for root, dirs, files in os.walk(clone_dir):
            for file in files:
                if file.endswith('.vmx'):
                    vmx_path = os.path.join(root, file)
                    # 检查VMX文件是否有VNC配置，并且路径中包含IP相关信息
                    if has_vnc_config(vmx_path):
                        # 尝试从VMX文件路径或内容中匹配IP
                        if is_vmx_for_ip(vmx_path, target_ip):
                            logger.info(f"根据IP匹配找到VMX文件: {vmx_path}")
                            return vmx_path
        
        # 如果仍然没找到，记录错误并返回None
        logger.error(f"无法找到IP {target_ip} 对应的VMX文件")
        
        return None
    except Exception as e:
        logger.error(f"查找VMX文件时出错: {str(e)}")
        return None

def has_vnc_config(vmx_path):
    """检查VMX文件中是否包含VNC配置"""
    try:
        with open(vmx_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # 检查是否包含VNC配置
            return 'RemoteDisplay.vnc.enabled' in content and 'RemoteDisplay.vnc.port' in content
    except Exception as e:
        logger.error(f"读取VMX文件 {vmx_path} 时出错: {str(e)}")
        return False

def is_vmx_for_ip(vmx_path, target_ip):
    """判断VMX文件是否对应指定的IP地址"""
    try:
        # 方法1: 检查文件路径中是否包含IP相关信息
        # 从IP地址提取最后一段作为标识符
        ip_parts = target_ip.split('.')
        if len(ip_parts) >= 4:
            last_octet = ip_parts[-1]  # 获取IP的最后一段
            # 检查VMX文件路径中是否包含这个数字
            if last_octet in vmx_path:
                logger.debug(f"VMX文件路径 {vmx_path} 包含IP最后一段 {last_octet}")
                return True
        
        # 方法2: 检查VMX文件内容中是否有IP相关配置
        with open(vmx_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # 检查是否包含目标IP
            if target_ip in content:
                logger.debug(f"VMX文件内容包含目标IP {target_ip}")
                return True
        
        # 方法3: 尝试从虚拟机名称推断
        # 提取虚拟机目录名称，通常包含虚拟机标识
        vm_dir = os.path.dirname(vmx_path)
        vm_name = os.path.basename(vm_dir)
        
        # 如果虚拟机名称中包含IP的最后一段，认为匹配
        if len(ip_parts) >= 4 and ip_parts[-1] in vm_name:
            logger.debug(f"虚拟机名称 {vm_name} 包含IP最后一段 {ip_parts[-1]}")
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"判断VMX文件 {vmx_path} 是否对应IP {target_ip} 时出错: {str(e)}")
        return False

def read_vnc_config_from_vmx(vmx_path):
    """从VMX文件中读取VNC配置"""
    try:
        vnc_config = {'port': None, 'password': None}
        
        with open(vmx_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line.startswith('RemoteDisplay.vnc.port'):
                    # 提取端口号
                    parts = line.split('=')
                    if len(parts) == 2:
                        port_value = parts[1].strip().strip('"')
                        vnc_config['port'] = port_value
                elif line.startswith('RemoteDisplay.vnc.password'):
                    # 提取密码
                    parts = line.split('=')
                    if len(parts) == 2:
                        password_value = parts[1].strip().strip('"')
                        vnc_config['password'] = password_value
        
        # 检查是否获取到了必要的配置
        if vnc_config['port'] and vnc_config['password']:
            return vnc_config
        else:
            return None
    except Exception as e:
        logger.error(f"读取VMX文件 {vmx_path} 的VNC配置时出错: {str(e)}")
        return None

def start_websockify(client_ip, vnc_port):
    """启动websockify进程"""
    try:
        # 为每个客户端分配一个唯一的WebSocket端口
        websocket_port = get_available_websocket_port()
        if not websocket_port:
            logger.error("无法分配WebSocket端口")
            return None
        
        # 停止之前的websockify进程（如果存在）
        stop_websockify(client_ip)
        
        # 启动websockify进程
        cmd = [
            sys.executable, '-m', 'websockify',
            '--web', os.path.join(os.path.dirname(__file__), 'web', 'static'),
            f'{websocket_port}',
            f'localhost:{vnc_port}'
        ]
        
        logger.info(f"启动websockify命令: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # 存储进程信息
        websockify_processes[client_ip] = {
            'process': process,
            'websocket_port': websocket_port,
            'vnc_port': vnc_port,
            'start_time': time.time()
        }
        
        # 等待一小段时间确保进程启动
        time.sleep(1)
        
        # 检查进程是否正常运行
        if process.poll() is None:
            logger.info(f"websockify进程启动成功: PID={process.pid}, WebSocket端口={websocket_port}")
            return websocket_port
        else:
            logger.error(f"websockify进程启动失败: 返回码={process.returncode}")
            if client_ip in websockify_processes:
                del websockify_processes[client_ip]
            return None
            
    except Exception as e:
        logger.error(f"启动websockify失败: {str(e)}")
        return None

def stop_websockify(client_ip):
    """停止指定客户端的websockify进程"""
    try:
        if client_ip in websockify_processes:
            process_info = websockify_processes[client_ip]
            process = process_info['process']
            
            if process.poll() is None:  # 进程仍在运行
                logger.info(f"停止websockify进程: PID={process.pid}")
                process.terminate()
                
                # 等待进程结束
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(f"websockify进程未能正常结束，强制终止: PID={process.pid}")
                    process.kill()
            
            del websockify_processes[client_ip]
            logger.info(f"websockify进程已停止: {client_ip}")
            
    except Exception as e:
        logger.error(f"停止websockify进程失败: {str(e)}")

def cleanup_all_websockify():
    """清理所有websockify进程和资源"""
    try:
        logger.info("开始清理所有websockify进程...")
        
        # 停止所有已知的websockify进程
        client_ips = list(websockify_processes.keys())
        for client_ip in client_ips:
            stop_websockify(client_ip)
        
        # 清空进程字典
        websockify_processes.clear()
        
        # 使用psutil查找并终止所有websockify进程
        import psutil
        killed_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # 检查是否是websockify进程
                if proc.info['cmdline'] and any('websockify' in str(arg) for arg in proc.info['cmdline']):
                    pid = proc.info['pid']
                    logger.info(f"发现websockify进程: PID={pid}, 命令行={proc.info['cmdline']}")
                    
                    # 终止进程
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                        killed_processes.append(pid)
                        logger.info(f"成功终止websockify进程: PID={pid}")
                    except psutil.TimeoutExpired:
                        proc.kill()
                        killed_processes.append(pid)
                        logger.warning(f"强制终止websockify进程: PID={pid}")
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        # 释放端口（通过终止占用6080+端口的进程）
        for port in range(6080, 6180):  # 检查常用的WebSocket端口范围
            try:
                for conn in psutil.net_connections():
                    if conn.laddr.port == port and conn.status == 'LISTEN':
                        try:
                            proc = psutil.Process(conn.pid)
                            if 'python' in proc.name().lower() or 'websockify' in ' '.join(proc.cmdline()):
                                logger.info(f"释放端口 {port}，终止进程 PID={conn.pid}")
                                proc.terminate()
                                try:
                                    proc.wait(timeout=3)
                                except psutil.TimeoutExpired:
                                    proc.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
            except Exception:
                continue
        
        logger.info(f"websockify进程清理完成，共终止 {len(killed_processes)} 个进程")
        return True
        
    except Exception as e:
        logger.error(f"清理websockify进程失败: {str(e)}")
        return False

def cleanup_all_vnc_connections():
    """清理所有VNC连接和资源"""
    try:
        logger.info("开始清理所有VNC连接...")
        
        # 清理WebSocket VNC连接
        session_ids = list(vnc_connections.keys())
        for session_id in session_ids:
            try:
                connection = vnc_connections[session_id]
                if 'socket' in connection and connection['socket']:
                    try:
                        # 检查套接字是否仍然有效
                        if hasattr(connection['socket'], 'fileno'):
                            connection['socket'].close()
                    except (OSError, AttributeError) as e:
                        # 忽略套接字已关闭或无效的错误
                        logger.debug(f"套接字已关闭或无效: {str(e)}")
                del vnc_connections[session_id]
                logger.info(f"清理VNC连接: {session_id}")
            except Exception as e:
                logger.error(f"清理VNC连接 {session_id} 失败: {str(e)}")
        
        # 清空连接字典
        vnc_connections.clear()
        
        # 清理websockify进程
        cleanup_all_websockify()
        
        logger.info("所有VNC连接和资源清理完成")
        return True
        
    except Exception as e:
        logger.error(f"清理VNC连接失败: {str(e)}")
        return False

def get_available_websocket_port():
    """获取可用的WebSocket端口"""
    import socket
    
    # 从6080开始尝试端口
    start_port = 6080
    max_attempts = 100
    
    for i in range(max_attempts):
        port = start_port + i
        try:
            # 检查端口是否被占用
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    
    logger.error(f"无法找到可用的WebSocket端口（尝试了{max_attempts}个端口）")
    return None

# VNC断开连接API
@app.route('/api/vnc/disconnect', methods=['POST'])
@login_required
def api_vnc_disconnect():
    """断开VNC连接"""
    try:
        data = request.get_json()
        client_ip = data.get('client_ip')
        
        if not client_ip:
            return jsonify({'success': False, 'message': '客户端IP不能为空'})
        
        # 停止websockify进程
        stop_websockify(client_ip)
        
        return jsonify({'success': True, 'message': 'VNC连接已断开'})
        
    except Exception as e:
        logger.error(f"断开VNC连接失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

# 清理所有VNC连接API
@app.route('/api/vnc/cleanup_all', methods=['POST'])
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

# 旧的VNC WebSocket代理代码（保留以防需要）
vnc_connections = {}

@socketio.on('vnc_connect')
def handle_vnc_connect(data):
    """处理VNC WebSocket连接"""
    try:
        client_ip = data.get('client_ip')
        if not client_ip:
            emit('vnc_error', {'message': '客户端IP不能为空'})
            return
        
        logger.info(f"WebSocket VNC连接请求: {client_ip}")
        
        # 查找VMX文件和VNC配置
        vmx_file = find_vmx_file_by_ip(client_ip)
        if not vmx_file:
            emit('vnc_error', {'message': f'未找到客户端IP {client_ip} 对应的虚拟机配置文件'})
            return
        
        vnc_config = read_vnc_config_from_vmx(vmx_file)
        if not vnc_config:
            emit('vnc_error', {'message': '虚拟机未启用VNC或配置不完整'})
            return
        
        # 创建VNC代理连接
        session_id = request.sid
        vnc_host = 'localhost'
        vnc_port = int(vnc_config['port'])
        
        try:
            # 创建到VNC服务器的socket连接
            vnc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 设置连接超时为10秒
            vnc_socket.settimeout(10.0)
            logger.info(f"尝试连接VNC服务器: {vnc_host}:{vnc_port}")
            vnc_socket.connect((vnc_host, vnc_port))
            logger.info(f"VNC socket连接成功: {vnc_host}:{vnc_port}")
            
            # 存储连接信息
            vnc_connections[session_id] = {
                'socket': vnc_socket,
                'config': vnc_config,
                'vmx_file': vmx_file,
                'client_ip': client_ip
            }
            
            # 启动数据转发线程
            thread = threading.Thread(target=vnc_proxy_worker, args=(session_id, vnc_socket))
            thread.daemon = True
            thread.start()
            
            emit('vnc_connected', {
                'host': vnc_host,
                'port': vnc_port,
                'password': vnc_config['password']
            })
            
            logger.info(f"VNC WebSocket连接成功: {client_ip} -> {vnc_host}:{vnc_port}")
            
        except Exception as e:
            logger.error(f"VNC socket连接失败: {str(e)}")
            emit('vnc_error', {'message': f'VNC连接失败: {str(e)}'})
            
    except Exception as e:
        logger.error(f"VNC WebSocket处理失败: {str(e)}")
        emit('vnc_error', {'message': str(e)})

@socketio.on('vnc_data')
def handle_vnc_data(data):
    """处理VNC数据传输"""
    session_id = request.sid
    if session_id in vnc_connections:
        try:
            vnc_socket = vnc_connections[session_id]['socket']
            # 解码并转发WebSocket数据到VNC服务器
            raw_data = base64.b64decode(data['data'])
            logger.debug(f"转发VNC数据: {len(raw_data)} 字节, 内容: {raw_data.hex()}")
            vnc_socket.send(raw_data)
        except Exception as e:
            logger.error(f"VNC数据转发失败: {str(e)}")
            emit('vnc_error', {'message': f'数据传输失败: {str(e)}'}) 
    else:
        logger.warning(f"收到数据但VNC连接不存在: {session_id}")
        emit('vnc_error', {'message': 'VNC连接不存在'})

@socketio.on('disconnect')
def handle_disconnect():
    """处理WebSocket断开连接"""
    session_id = request.sid
    if session_id in vnc_connections:
        try:
            vnc_connections[session_id]['socket'].close()
            del vnc_connections[session_id]
            logger.info(f"VNC连接已断开: {session_id}")
        except Exception as e:
            logger.error(f"断开VNC连接时出错: {str(e)}")

def vnc_proxy_worker(session_id, vnc_socket):
    """VNC代理工作线程，将VNC服务器数据转发到WebSocket"""
    try:
        # 设置socket超时为5秒，给RFB握手更多时间
        vnc_socket.settimeout(5.0)
        
        logger.info(f"VNC代理工作线程启动: {session_id}")
        logger.info(f"VNC socket状态: {vnc_socket.getsockname()} -> {vnc_socket.getpeername()}")
        
        while session_id in vnc_connections:
            try:
                # 从VNC服务器接收数据
                data = vnc_socket.recv(4096)
                if not data:
                    logger.info(f"VNC服务器关闭连接: {session_id}")
                    break
                
                logger.debug(f"VNC代理收到数据: {len(data)} 字节, 内容: {data.hex()}")
                
                # 分析RFB协议数据
                if len(data) >= 12 and data.startswith(b'RFB '):
                    version = data[:12].decode('ascii', errors='ignore')
                    logger.info(f"RFB版本握手: {version.strip()}")
                elif len(data) == 1:
                    logger.info(f"RFB安全类型选择: {data[0]}")
                elif len(data) == 2 and data[0] in [1, 2]:
                    logger.info(f"RFB安全类型数量: {data[0]}, 类型: {data[1]}")
                elif len(data) == 16:
                    logger.info(f"RFB认证挑战: {data.hex()}")
                elif len(data) == 4:
                    result = int.from_bytes(data, 'big')
                    if result == 0:
                        logger.info("RFB认证成功")
                    else:
                        logger.warning(f"RFB认证失败: {result}")
                
                # 将数据编码为base64并发送到WebSocket
                encoded_data = base64.b64encode(data).decode('utf-8')
                socketio.emit('vnc_data', {'data': encoded_data}, room=session_id)
                
            except socket.timeout:
                # 超时是正常的，继续循环
                continue
            except ConnectionResetError:
                logger.info(f"VNC连接被重置: {session_id}")
                break
            except OSError as e:
                if e.winerror == 10053:  # 连接被主机软件中止
                    logger.warning(f"VNC连接被服务器中止: {session_id}, 错误码: {e.winerror}")
                    # 尝试重新连接
                    socketio.emit('vnc_reconnect_needed', {'reason': 'connection_aborted'}, room=session_id)
                else:
                    logger.error(f"VNC代理网络错误: {str(e)}, 错误码: {getattr(e, 'winerror', 'N/A')}")
                break
            except Exception as e:
                logger.error(f"VNC代理数据接收失败: {str(e)}")
                break
                
    except Exception as e:
        logger.error(f"VNC代理工作线程异常: {str(e)}")
    finally:
        # 清理连接
        logger.info(f"清理VNC连接: {session_id}")
        if session_id in vnc_connections:
            try:
                vnc_connections[session_id]['socket'].close()
                del vnc_connections[session_id]
            except:
                pass
        socketio.emit('vnc_disconnected', room=session_id)

# VNC控制操作API
@app.route('/api/vnc_refresh', methods=['POST'])
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

@app.route('/api/vnc_send_keys', methods=['POST'])
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

def find_vnc_session_by_ip(client_ip):
    """根据客户端IP查找VNC会话"""
    for session_id, connection in vnc_connections.items():
        if connection.get('client_ip') == client_ip:
            return session_id
    return None

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
        
        # 在虚拟机模板目录中查找匹配的.vmx文件
        vm_template_dir = template_dir  # 使用从config导入的虚拟机模板目录
        if os.path.exists(vm_template_dir):
            for root, dirs, files in os.walk(vm_template_dir):
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
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
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
                start_time = datetime.now()
                print(f"[DEBUG] 快照命令开始时间: {start_time}")
                
                result = subprocess.run(snapshot_cmd, capture_output=True, text=True, timeout=120)
                
                # 记录命令结束时间
                end_time = datetime.now()
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
        
        # 验证克隆数量与五码数量是否匹配
        if clone_count > len(wuma_codes):
            error_msg = f'克隆数量({clone_count})超过可用五码数量({len(wuma_codes)})，请确保五码数量足够'
            add_task_log(task_id, 'error', error_msg)
            print(f"[DEBUG] 错误: {error_msg}")
            task['status'] = 'failed'
            return
        elif clone_count < len(wuma_codes):
            warning_msg = f'五码数量({len(wuma_codes)})多于克隆数量({clone_count})，将使用前{clone_count}个五码'
            add_task_log(task_id, 'warning', warning_msg)
            print(f"[DEBUG] 警告: {warning_msg}")
            # 截取需要的五码数量
            wuma_codes = wuma_codes[:clone_count]
        
        # 生成统一的时间戳，用于所有虚拟机
        unified_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        print(f"[DEBUG] 使用统一时间戳: {unified_timestamp}")
        
        add_task_log(task_id, 'info', f'找到 {len(wuma_codes)} 个有效五码，需要克隆 {clone_count} 个虚拟机，数量匹配验证通过')
        
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
                
                # 生成虚拟机名称和文件夹名称（使用统一时间戳）
                timestamp = unified_timestamp
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
                start_time = datetime.now()
                print(f"[DEBUG] 命令开始时间: {start_time}")
                
                result = subprocess.run(clone_cmd, capture_output=True, text=True, timeout=300)
                
                # 记录命令结束时间
                end_time = datetime.now()
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
                    
                    # 添加VNC配置
                    vnc_port = get_next_vnc_port()
                    if add_vnc_config_to_vmx(vm_file_path, vnc_port):
                        add_task_log(task_id, 'info', f'虚拟机 {vm_name} 的VNC配置已添加，端口: {vnc_port}')
                        print(f"[DEBUG] VNC配置添加成功，端口: {vnc_port}")
                    else:
                        add_task_log(task_id, 'warning', f'虚拟机 {vm_name} 的VNC配置添加失败')
                        print(f"[DEBUG] VNC配置添加失败")
                    
                    # 如果配置了自动启动或者配置了五码文件（需要启动虚拟机进行后续配置）
                    should_start = params.get('autoStart') == 'true' or params.get('configPlist')
                    if should_start:
                        start_reason = "用户勾选自动启动" if params.get('autoStart') == 'true' else "需要进行五码配置"
                        start_cmd = [vmrun_path, 'start', vm_file_path, 'nogui']
                        print(f"[DEBUG] 启动虚拟机原因: {start_reason}")
                        print(f"[DEBUG] 启动命令: {' '.join(start_cmd)}")
                        add_task_log(task_id, 'info', f'启动虚拟机 ({start_reason}): vmrun start {vm_file_path}')
                        
                        # 记录启动命令开始时间
                        start_time = datetime.now()
                        print(f"[DEBUG] 启动命令开始时间: {start_time}")
                        
                        result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=60)
                        
                        # 记录启动命令结束时间
                        end_time = datetime.now()
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
        
        # 如果有成功克隆的虚拟机且配置了五码文件，启动动态监控和配置流程
        if task['stats']['success'] > 0 and params.get('configPlist'):
            add_task_log(task_id, 'info', '开始启动虚拟机监控和自动配置流程...')
            print(f"[DEBUG] 开始启动虚拟机监控和自动配置流程...")
            
            try:
                # 收集成功克隆的虚拟机信息（使用相同的统一时间戳）
                cloned_vms_info = []
                for i in range(clone_count):
                    timestamp = unified_timestamp  # 使用克隆时的统一时间戳
                    vm_name_pattern = params['namingPattern']
                    if vm_name_pattern == 'custom':
                        vm_name_pattern = params.get('customNamingPattern', 'VM_{timestamp}_{index}')
                    
                    vm_name_without_ext_generated = vm_name_pattern.replace('{timestamp}', timestamp).replace('{index}', str(i+1)).replace('{vmname}', vm_name_without_ext)
                    vm_folder_name = vm_name_without_ext_generated
                    vm_folder_path = os.path.join(target_dir, vm_folder_name)
                    vm_name = vm_name_without_ext_generated + '.vmx'
                    vm_file_path = os.path.join(vm_folder_path, vm_name)
                    
                    print(f"[DEBUG] 检查虚拟机文件: {vm_file_path}")
                    if os.path.exists(vm_file_path):
                        cloned_vms_info.append({
                            'name': vm_name_without_ext_generated,
                            'path': vm_file_path
                        })
                        print(f"[DEBUG] 找到成功克隆的虚拟机: {vm_name_without_ext_generated}")
                    else:
                        print(f"[DEBUG] 虚拟机文件不存在: {vm_file_path}")
                
                if cloned_vms_info:
                    add_task_log(task_id, 'info', f'找到 {len(cloned_vms_info)} 个成功克隆的虚拟机，启动监控线程')
                    print(f"[DEBUG] 找到 {len(cloned_vms_info)} 个成功克隆的虚拟机")
                    
                    # 更新任务状态，增加监控阶段
                    task['monitoring'] = {
                        'status': 'running',
                        'total_vms': len(cloned_vms_info),
                        'completed_vms': 0,
                        'success_vms': 0,
                        'failed_vms': 0,
                        'restart_progress': {
                            'current': 0,
                            'total': len(cloned_vms_info)
                        },
                        'wuma_progress': {
                            'current': 0,
                            'total': len(cloned_vms_info)
                        }
                    }
                    
                    # 为每个虚拟机启动独立的监控线程
                    for vm_info in cloned_vms_info:
                        vm_name = vm_info['name']
                        vm_path = vm_info['path']
                        
                        # 启动监控线程
                        monitor_thread = threading.Thread(
                            target=monitor_vm_and_configure,
                            args=(task_id, vm_name, vm_path, params['configPlist']),
                            daemon=True
                        )
                        monitor_thread.start()
                        
                        add_task_log(task_id, 'info', f'已启动虚拟机 {vm_name} 的监控线程')
                        print(f"[DEBUG] 已启动虚拟机 {vm_name} 的监控线程")
                        
                        # 避免同时启动太多线程
                        time.sleep(2)
                    
                    add_task_log(task_id, 'info', '所有虚拟机监控线程已启动，将在后台继续执行')
                    print(f"[DEBUG] 所有虚拟机监控线程已启动")
                    
                    # 不要立即标记任务完成，让监控线程继续运行
                    # 任务状态保持为'running'，直到所有监控完成
                    add_task_log(task_id, 'info', '克隆阶段完成，正在进行虚拟机配置...')
                    
                else:
                    add_task_log(task_id, 'warning', '未找到成功克隆的虚拟机，跳过监控配置')
                    print(f"[DEBUG] 未找到成功克隆的虚拟机，跳过监控配置")
                    
                    # 没有监控任务时才标记完成
                    if task['stats']['error'] == 0:
                        task['status'] = 'completed'
                        add_task_log(task_id, 'success', f'所有虚拟机克隆完成！成功: {task["stats"]["success"]}')
                        print(f"[DEBUG] 所有虚拟机克隆完成！成功: {task['stats']['success']}")
                    else:
                        task['status'] = 'completed_with_errors'
                        add_task_log(task_id, 'warning', f'克隆任务完成，但有错误。成功: {task["stats"]["success"]}, 失败: {task["stats"]["error"]}')
                        print(f"[DEBUG] 克隆任务完成，但有错误。成功: {task['stats']['success']}, 失败: {task['stats']['error']}")
                    
            except Exception as e:
                add_task_log(task_id, 'error', f'启动虚拟机监控时发生错误: {str(e)}')
                print(f"[DEBUG] 启动虚拟机监控时发生错误: {str(e)}")
                
                # 发生错误时才标记完成
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

def get_next_vnc_port():
    """获取下一个可用的VNC端口"""
    try:
        config_ini_path = os.path.join('web', 'config', 'config.ini')
        
        # 读取当前的vnc_end_port
        current_port = vnc_start_port  # 默认从config.py中的起始端口开始
        
        if os.path.exists(config_ini_path):
            with open(config_ini_path, 'r', encoding='utf-8') as f:
                content = f.read()
                for line in content.split('\n'):
                    if line.strip().startswith('vnc_end_port='):
                        current_port = int(line.split('=')[1].strip())
                        break
        
        # 分配下一个端口
        next_port = current_port + 1
        
        # 更新config.ini中的vnc_end_port
        with open(config_ini_path, 'w', encoding='utf-8') as f:
            f.write(f'vnc_end_port={next_port}\n')
        
        print(f"[DEBUG] 分配VNC端口: {next_port}，已更新config.ini")
        return next_port
        
    except Exception as e:
        print(f"[DEBUG] 获取VNC端口失败: {str(e)}")
        # 如果出错，返回默认端口
        return vnc_start_port

def add_vnc_config_to_vmx(vmx_file_path, vnc_port):
    """在VMX文件中添加VNC配置参数"""
    try:
        print(f"[DEBUG] 开始添加VNC配置到vmx文件: {vmx_file_path}")
        print(f"[DEBUG] VNC端口: {vnc_port}")
        
        # 检查文件是否存在
        if not os.path.exists(vmx_file_path):
            print(f"[DEBUG] vmx文件不存在: {vmx_file_path}")
            return False
        
        # 读取vmx文件
        with open(vmx_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"[DEBUG] 读取到 {len(lines)} 行内容")
        
        # 检查是否已存在VNC配置，如果存在则更新，否则添加
        vnc_configs = {
            'RemoteDisplay.vnc.enabled': 'TRUE',
            'RemoteDisplay.vnc.port': str(vnc_port),
            'RemoteDisplay.vnc.password': vnc_default_password
        }
        
        updated_configs = set()
        
        # 查找并更新已存在的VNC配置
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            for config_key, config_value in vnc_configs.items():
                if line_stripped.startswith(config_key):
                    old_line = line_stripped
                    new_line = f'{config_key} = "{config_value}"\n'
                    lines[i] = new_line
                    updated_configs.add(config_key)
                    print(f"[DEBUG] 更新VNC配置: {old_line} -> {new_line.strip()}")
                    break
        
        # 添加未找到的VNC配置
        for config_key, config_value in vnc_configs.items():
            if config_key not in updated_configs:
                new_line = f'{config_key} = "{config_value}"\n'
                lines.append(new_line)
                print(f"[DEBUG] 添加VNC配置: {new_line.strip()}")
        
        # 写回文件
        with open(vmx_file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print(f"[DEBUG] VNC配置添加成功")
        return True
        
    except Exception as e:
        print(f"[DEBUG] 添加VNC配置失败: {str(e)}")
        return False

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
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message
        }
        task['logs'].append(log_entry)
        
        # 强制刷新，确保前端能立即收到日志更新
        import sys
        sys.stdout.flush()
        
        # 同时写入日志文件
        current_date = datetime.now().strftime('%Y-%m-%d')
        log_file_path = os.path.join(log_dir, f'task_{task_id}_{current_date}.log')
        try:
            with open(log_file_path, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f'[{timestamp}] [{level.upper()}] {message}\n')
                f.flush()  # 强制刷新文件缓冲区
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
                    print(f"[DEBUG] 完成信号序列化失败: {str(e)}")
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
                
                # 发送统计更新（只在有新数据时发送）
                if has_new_data:
                    try:
                        stats_data = {
                            'type': 'stats',
                            'stats': task['stats']
                        }
                        yield f"data: {json.dumps(stats_data, ensure_ascii=False)}\n\n"
                    except Exception as e:
                        print(f"[DEBUG] 统计数据序列化失败: {str(e)}")
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
        start_time = datetime.now()
        print(f"[DEBUG] 启动命令开始时间: {start_time}")
        
        result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=60)
        
        # 记录命令结束时间
        end_time = datetime.now()
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
        start_time = datetime.now()
        print(f"[DEBUG] 停止命令开始时间: {start_time}")
        
        result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=60)
        
        # 记录命令结束时间
        end_time = datetime.now()
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
        stop_start_time = datetime.now()
        print(f"[DEBUG] 重启-停止命令开始时间: {stop_start_time}")
        
        stop_result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=60)
        
        # 记录停止命令结束时间
        stop_end_time = datetime.now()
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
        start_start_time = datetime.now()
        print(f"[DEBUG] 重启-启动命令开始时间: {start_start_time}")
        
        start_result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=60)
        
        # 记录启动命令结束时间
        start_end_time = datetime.now()
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
                # 虚拟机不在运行列表中，检查是否处于挂起状态
                print(f"[DEBUG] 未找到运行中的虚拟机: {vm_name}，检查是否挂起")
                
                # 检查.vmss文件是否存在（挂起状态文件）
                vm_dir = os.path.dirname(vm_path)
                vmss_files = [f for f in os.listdir(vm_dir) if f.endswith('.vmss')]
                if vmss_files:
                    print(f"[DEBUG] 发现挂起状态文件: {vmss_files}")
                    return 'suspended'
                
                return 'stopped'
        
        return 'stopped'
        
    except Exception as e:
        print(f"[DEBUG] 获取虚拟机状态失败: {str(e)}")
        return 'unknown'


def get_vm_suspend_time(vm_path):
    """获取虚拟机挂起时间"""
    try:
        vm_dir = os.path.dirname(vm_path)
        vm_name = os.path.splitext(os.path.basename(vm_path))[0]
        
        # 查找.vmss文件（挂起状态文件）
        vmss_files = [f for f in os.listdir(vm_dir) if f.endswith('.vmss')]
        
        if vmss_files:
            # 获取最新的.vmss文件的修改时间
            latest_vmss = None
            latest_time = None
            
            for vmss_file in vmss_files:
                vmss_path = os.path.join(vm_dir, vmss_file)
                mtime = os.path.getmtime(vmss_path)
                if latest_time is None or mtime > latest_time:
                    latest_time = mtime
                    latest_vmss = vmss_path
            
            if latest_time:
                # 将时间戳转换为ISO格式字符串
                suspend_time = datetime.fromtimestamp(latest_time)
                return suspend_time.isoformat()
        
        return None
        
    except Exception as e:
        logger.error(f"获取虚拟机挂起时间失败: {str(e)}")
        return None


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
                    start_time = datetime.now()
                    print(f"[DEBUG] getGuestIPAddress命令开始时间: {start_time}")
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    # 记录命令结束时间
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    print(f"[DEBUG] getGuestIPAddress命令结束时间: {end_time}")
                    print(f"[DEBUG] getGuestIPAddress命令执行时长: {duration} 秒")
                    print(f"[DEBUG] getGuestIPAddress命令返回码: {result.returncode}")
                    print(f"[DEBUG] getGuestIPAddress命令输出: {result.stdout}")
                    if result.stderr:
                        print(f"[DEBUG] getGuestIPAddress命令错误: {result.stderr}")
                    
                    # 检查特定的错误码4294967295，但不执行强制重启
                    if result.returncode == 4294967295:
                        logger.warning(f"检测到虚拟机 {vm_name} 卡死（返回码: 4294967295），但不执行强制重启")
                        print(f"[DEBUG] 检测到虚拟机卡死，返回码: 4294967295，但不执行强制重启")
                        return None
                    
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
    try:
        # 如果vm_name已经是完整路径，直接检查是否存在
        if vm_name.endswith('.vmx') and os.path.exists(vm_name):
            logger.debug(f"虚拟机文件路径有效: {vm_name}")
            return vm_name
        
        # 如果是完整路径但文件不存在，记录警告
        if vm_name.endswith('.vmx'):
            logger.warning(f"虚拟机文件不存在: {vm_name}")
            return None
        
        # 如果是简单名称，则在目录中搜索
        vm_dir = r'D:\macos_vm\NewVM'
        if os.path.exists(vm_dir):
            for root, dirs, files in os.walk(vm_dir):
                for file in files:
                    if file.endswith('.vmx') and vm_name in file:
                        return os.path.join(root, file)
        return None
        
    except Exception as e:
        logger.error(f"查找虚拟机文件失败: {str(e)}")
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
    """用户登出"""
    username = session.get('username', 'unknown')
    session.clear()
    logger.info(f"用户 {username} 已登出")
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
        # 使用新的通用脚本扫描函数
        scripts = scan_scripts_from_directories()
        
        logger.info(f"成功获取 {len(scripts)} 个脚本文件")
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

@app.route('/api/script/content/<script_name>')
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
        result = execute_remote_script(vm_ip, 'wx', f'{script_remote_path}/run_debug_wuma.sh')
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
        result = execute_remote_script(vm_ip, 'wx', f'{script_remote_path}/run_debug_ju.sh')
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
    """通过SSH互信执行目录脚本并获取输出"""
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
        check_command = f"ls -la {script_name}"
        ssh_log.append(f"[SSH] 检查脚本是否存在: {check_command}")
        stdin, stdout, stderr = ssh.exec_command(check_command)
        check_output = stdout.read().decode().strip()
        check_error = stderr.read().decode().strip()
        
        if not check_output:
            ssh_log.append(f"[SSH] 脚本不存在: {script_name}")
            ssh.close()
            return False, f"脚本 {script_name} 不存在", "\n".join(ssh_log)
        
        ssh_log.append(f"[SSH] 脚本存在: {check_output}")
        
        # 检查脚本执行权限
        chmod_command = f"chmod +x {script_name}"
        ssh_log.append(f"[SSH] 添加执行权限: {chmod_command}")
        stdin, stdout, stderr = ssh.exec_command(chmod_command)
        chmod_error = stderr.read().decode().strip()
        if chmod_error:
            ssh_log.append(f"[SSH] 添加执行权限失败: {chmod_error}")
        else:
            ssh_log.append("[SSH] 执行权限添加成功")
        
        # 执行家目录脚本命令
        command = f"{script_name}"
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

@app.route('/api/vm_10_12_suspend', methods=['POST'])
@login_required
def api_vm_10_12_suspend():
    """挂起10.12目录虚拟机"""
    return vm_operation_generic('suspend', '10.12目录', VM_DIRS['10_12'])

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
        from config import wuma_config_delete_dir
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

#克隆后等待执行更改五码的操作
def batch_change_wuma_core(selected_vms, config_file_path, task_id=None):
    """批量更改五码核心函数"""
    logger.info(f"开始批量更改五码核心处理，虚拟机数量: {len(selected_vms)}")
    logger.info(f"使用配置文件: {config_file_path}")
    
    def log_message(level, message):
        """统一日志记录函数"""
        logger.info(message)
        if task_id:
            add_task_log(task_id, level, message)
    
    try:
        if not selected_vms:
            return {
                'status': 'error',
                'message': '没有选中任何虚拟机'
            }
        
        if not os.path.exists(config_file_path):
            return {
                'status': 'error',
                'message': f'配置文件 {config_file_path} 不存在'
            }
        
        # 读取五码配置文件
        with open(config_file_path, 'r', encoding='utf-8') as f:
            wuma_lines = f.readlines()
        
        # 过滤有效行
        valid_wuma_lines = [line.strip() for line in wuma_lines if line.strip() and is_valid_wuma_file_line(line.strip())]
        
        if not valid_wuma_lines:
            return {
                'status': 'error',
                'message': '配置文件中没有有效的五码数据'
            }
        
        # 检查五码数据是否足够
        if len(valid_wuma_lines) < len(selected_vms):
            return {
                'status': 'error',
                'message': f'五码数据不足，需要 {len(selected_vms)} 个，但只有 {len(valid_wuma_lines)} 个'
            }
        
        # 验证选中的虚拟机是否都在运行
        vmrun_path = get_vmrun_path()
        
        list_cmd = [vmrun_path, 'list']
        logger.debug(f"执行vmrun命令: {list_cmd}")
        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return {
                'status': 'error',
                'message': f'获取运行中虚拟机列表失败: {result.stderr}'
            }
        
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
                log_message('warning', f'虚拟机 {vm_name} 不在运行状态，跳过处理')
                continue
        
        # 读取temp.plist模板
        plist_template_path = os.path.join(plist_template_dir, 'temp.plist')
        logger.info(f"检查temp.plist模板文件: {plist_template_path}")
        if not os.path.exists(plist_template_path):
            logger.error(f"temp.plist模板文件不存在: {plist_template_path}")
            return {
                'status': 'error',
                'message': f'temp.plist模板文件不存在: {plist_template_path}'
            }
        
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
                log_message('warning', f'五码数据不足，跳过虚拟机: {vm_name}')
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
                log_message('error', f'未找到虚拟机 {vm_name} 的运行路径')
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
                    log_message('error', f'五码格式错误: {wuma_line}')
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
                plist_file_path = os.path.join(wuma_config_install_dir, plist_filename)
                os.makedirs(os.path.dirname(plist_file_path), exist_ok=True)
                
                with open(plist_file_path, 'w', encoding='utf-8') as f:
                    f.write(plist_content)
                
                logger.info(f"生成plist文件: {plist_file_path}")
                
                # 获取虚拟机IP
                vm_ip = get_vm_ip(vm_name)
                logger.info(f"获取虚拟机 {vm_name} 的IP: {vm_ip}")
                if not vm_ip:
                    log_message('error', f'无法获取虚拟机 {vm_name} 的IP')
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': '无法获取虚拟机IP'
                    })
                    continue
                
                # 更新重启进度 - 开始重启虚拟机
                if task_id and task_id in clone_tasks:
                    task = clone_tasks[task_id]
                    if 'monitoring' in task:
                        task['monitoring']['restart_progress']['current'] += 1
                        restart_progress = {
                            'current': task['monitoring']['restart_progress']['current'],
                            'total': task['monitoring']['restart_progress']['total']
                        }
                        # 发送重启进度更新
                        progress_data = {
                            'type': 'monitoring_progress',
                            'vm_name': vm_name,
                            'restart_progress': restart_progress
                        }
                        task['logs'].append(progress_data)
                        log_message('info', f'虚拟机 {vm_name} 重启进度: {restart_progress["current"]}/{restart_progress["total"]}')
                        
                        # 强制刷新，确保前端能立即收到更新
                        import sys
                        sys.stdout.flush()
                
                # 执行mount_efi.sh脚本
                mount_cmd = f'ssh -o StrictHostKeyChecking=no {vm_username}@{vm_ip} "{script_remote_path}/mount_efi.sh"'
                logger.info(f"执行mount命令: {mount_cmd}")
                mount_result = subprocess.run(mount_cmd, shell=True, capture_output=True, text=True, timeout=60)
                
                if mount_result.returncode != 0:
                    logger.warning(f"mount_efi.sh执行失败: {mount_result.stderr}")
                    # 继续执行，不中断流程
                else:
                    logger.info(f"mount_efi.sh执行成功")
                
                # 传输plist文件到虚拟机
                scp_cmd = f'scp -o StrictHostKeyChecking=no "{plist_file_path}" {vm_username}@{vm_ip}:{boot_config_path}'
                logger.info(f"执行scp命令: {scp_cmd}")
                scp_result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True, timeout=60)
                
                if scp_result.returncode != 0:
                    log_message('error', f'文件传输失败: {scp_result.stderr}')
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': f'文件传输失败: {scp_result.stderr}'
                    })
                    continue
                else:
                    logger.info(f"文件传输成功")
                
                # 备份已使用的五码
                config_filename = os.path.basename(config_file_path)
                backup_config_file = os.path.join(backup_dir, f'{config_filename}_install.bak')
                
                # 追加到备份配置文件
                with open(backup_config_file, 'a', encoding='utf-8') as f:
                    f.write(wuma_line + '\n')
                
                used_wuma_lines.append(wuma_line)
                
                # 更新更改五码进度 - 五码配置完成
                if task_id and task_id in clone_tasks:
                    task = clone_tasks[task_id]
                    if 'monitoring' in task:
                        task['monitoring']['wuma_progress']['current'] += 1
                        wuma_progress = {
                            'current': task['monitoring']['wuma_progress']['current'],
                            'total': task['monitoring']['wuma_progress']['total']
                        }
                        # 发送更改五码进度更新
                        progress_data = {
                            'type': 'monitoring_progress',
                            'vm_name': vm_name,
                            'wuma_progress': wuma_progress
                        }
                        task['logs'].append(progress_data)
                        log_message('info', f'虚拟机 {vm_name} 更改五码进度: {wuma_progress["current"]}/{wuma_progress["total"]}')
                        
                        # 强制刷新，确保前端能立即收到更新
                        import sys
                        sys.stdout.flush()                
                results.append({
                    'vm_name': vm_name,
                    'success': True,
                    'message': '批量更改五码成功'
                })
                
                log_message('success', f'虚拟机 {vm_name} 批量更改五码完成')
                
            except Exception as e:
                log_message('error', f'处理虚拟机 {vm_name} 时出错: {str(e)}')
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
        
        log_message('info', f'批量更改五码完成 - 成功: {success_count}/{total_count}')
        
        return {
            'status': 'success',
            'message': f'批量更改五码完成！成功处理 {success_count}/{total_count} 个虚拟机',
            'results': results,
            'success_count': success_count,
            'total_count': total_count
        }
        
    except Exception as e:
        error_msg = f'批量更改五码失败: {str(e)}'
        logger.error(error_msg)
        if task_id:
            add_task_log(task_id, 'error', error_msg)
        return {
            'status': 'error',
            'message': error_msg
        }

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
        
        # 构建配置文件路径
        config_dir = wuma_config_dir
        if not default_config.endswith('.txt'):
            config_file_path = os.path.join(config_dir, f'{default_config}.txt')
        else:
            config_file_path = os.path.join(config_dir, default_config)
        
        # 调用核心函数
        result = batch_change_wuma_core(selected_vms, config_file_path)
        
        # 如果五码更改成功，自动执行批量更改JU值任务
        if result['status'] == 'success' and result['success_count'] > 0:
            # 获取成功更改五码的虚拟机列表
            successful_vms = [r['vm_name'] for r in result['results'] if r['success']]
            logger.info(f"开始为成功更改五码的虚拟机执行批量更改JU值: {successful_vms}")
            
            # 创建JU值更改任务ID
            ju_task_id = f"batch_change_ju_{int(time.time())}"
            tasks[ju_task_id] = {
                'status': 'running',
                'progress': 0,
                'total': len(successful_vms),
                'current': 0,
                'results': [],
                'logs': []
            }
            
            # 启动JU值更改后台任务
            import threading
            thread = threading.Thread(target=batch_change_ju_worker, args=(ju_task_id, successful_vms))
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'message': f'{result["message"]}，正在自动执行JU值更改',
                'results': result['results'],
                'ju_task_id': ju_task_id
            })
        else:
            return jsonify({
                'success': result['status'] == 'success',
                'message': result['message'],
                'results': result.get('results', [])
            })
        
        if not selected_vms:
            return jsonify({
                'success': False,
                'message': '没有选中任何虚拟机'
            })
        
        # 调用批量更改五码核心函数
        results = batch_change_wuma_core(selected_vms, default_config)
        
        # 检查是否有错误返回
        if 'success' in results and not results['success']:
            return jsonify(results)
        
        success_count = sum(1 for r in results if r['success'])
        total_count = len(results)
        
        logger.info(f"批量更改五码完成 - 成功: {success_count}/{total_count}")
        
        # 如果五码更改成功，自动执行批量更改JU值任务
        if success_count > 0:
            # 获取成功更改五码的虚拟机列表
            successful_vms = [r['vm_name'] for r in results if r['success']]
            logger.info(f"开始为成功更改五码的虚拟机执行批量更改JU值: {successful_vms}")
            
            # 创建JU值更改任务ID
            ju_task_id = f"batch_change_ju_{int(time.time())}"
            tasks[ju_task_id] = {
                'status': 'running',
                'progress': 0,
                'total': len(successful_vms),
                'current': 0,
                'results': [],
                'logs': []
            }
            
            # 启动JU值更改后台任务
            import threading
            thread = threading.Thread(target=batch_change_ju_worker, args=(ju_task_id, successful_vms))
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'message': f'批量更改五码完成！成功处理 {success_count}/{total_count} 个虚拟机，正在自动执行JU值更改',
                'results': results,
                'ju_task_id': ju_task_id
            })
        else:
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
                test_cmd = f'ssh -o StrictHostKeyChecking=no wx@{vm_ip} "{script_remote_path}/test.sh"'
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
                    'message': '五码和JU值更改完毕，虚拟机正在重启中'
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

# Apple ID管理相关API
@app.route('/api/appleid_files')
@login_required
def api_appleid_files():
    """获取Apple ID文件列表"""
    logger.info("收到获取Apple ID文件列表请求")
    try:
        files = []
        # 从配置文件读取目录路径
        from config import appleid_unused_dir
        id_dir = os.path.join(project_root, appleid_unused_dir)
        
        # 确保ID目录存在
        if not os.path.exists(id_dir):
            os.makedirs(id_dir, exist_ok=True)
            logger.info("创建ID_unused目录")
        
        # 查找ID目录下的所有.txt文件
        if os.path.exists(id_dir):
            for filename in os.listdir(id_dir):
                if filename.endswith('.txt'):
                    file_path = os.path.join(id_dir, filename)
                    
                    # 获取文件信息
                    try:
                        stat = os.stat(file_path)
                        files.append({
                            'name': filename,
                            'display_name': filename,
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        })
                        logger.info(f"发现Apple ID文件: {filename}")
                    except Exception as e:
                        logger.warning(f"获取文件信息失败 {filename}: {str(e)}")
            
            # 按名称排序
            files.sort(key=lambda x: x['name'])
            
            logger.info(f"找到 {len(files)} 个Apple ID文件")
            
            return jsonify({
                'success': True,
                'files': files
            })
        
    except Exception as e:
        logger.error(f"获取Apple ID文件列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取Apple ID文件列表失败: {str(e)}'
        })

@app.route('/api/appleid_file_content')
@login_required
def api_appleid_file_content():
    """获取Apple ID文件内容"""
    logger.info("收到获取Apple ID文件内容请求")
    try:
        filename = request.args.get('file')
        if not filename:
            return jsonify({
                'success': False,
                'message': '未指定文件名'
            })
        
        # 从配置文件读取目录路径
        from config import appleid_unused_dir
        file_path = os.path.join(project_root, appleid_unused_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': f'文件不存在: {filename}'
            })
        
        # 读取文件内容，尝试多种编码
        content = ""
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin-1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read().strip()
                logger.info(f"成功使用 {encoding} 编码读取文件 {filename}")
                break
            except UnicodeDecodeError:
                logger.warning(f"使用 {encoding} 编码读取文件 {filename} 失败，尝试下一种编码")
                continue
            except Exception as e:
                logger.error(f"读取文件 {filename} 时发生错误: {str(e)}")
                continue
        
        if not content:
            # 当文件为空时，返回成功状态而不是错误
            logger.info(f"文件 {filename} 为空，返回空内容")
            return jsonify({
                'success': True,
                'file_info': {
                    'name': filename,
                    'size': 0,
                    'lines': 0,
                    'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S') if os.path.exists(file_path) else ''
                },
                'content': []
            })
        
        lines = content.split('\n') if content else []
        valid_lines = []
        
        for line in lines:
            line = line.strip()
            if line and '----' in line:
                parts = line.split('----')
                if len(parts) >= 4:
                    valid_lines.append(line)
        
        # 获取文件信息
        stat = os.stat(file_path)
        file_info = {
            'name': filename,
            'size': stat.st_size,
            'lines': len(valid_lines),
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        logger.info(f"成功读取Apple ID文件 {filename}, 有效行数: {len(valid_lines)}")
        
        return jsonify({
            'success': True,
            'file_info': file_info,
            'content': valid_lines
        })
        
    except Exception as e:
        logger.error(f"获取Apple ID文件内容失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取Apple ID文件内容失败: {str(e)}'
        })

@app.route('/api/appleid_upload', methods=['POST'])
@login_required
def api_appleid_upload():
    """上传Apple ID文件"""
    logger.info("收到Apple ID文件上传请求")
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': '未找到上传的文件'
            })
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': '未选择文件'
            })
        
        # 检查文件扩展名
        if not file.filename.lower().endswith(('.txt', '.csv')):
            return jsonify({
                'success': False,
                'message': '只支持 .txt 和 .csv 格式的文件'
            })
        
        # 获取自定义文件名
        custom_filename = request.form.get('custom_filename', '').strip()
        if custom_filename:
            # 确保文件名安全
            import re
            custom_filename = re.sub(r'[^\w\-_.]', '_', custom_filename)
            filename = f"{custom_filename}.txt"
        else:
            # 使用原文件名，但确保是.txt格式
            base_name = os.path.splitext(file.filename)[0]
            filename = f"{base_name}.txt"
        
        # 确保ID_unused目录存在
        from config import appleid_unused_dir
        id_dir = os.path.join(project_root, appleid_unused_dir)
        os.makedirs(id_dir, exist_ok=True)
        
        # 检查文件是否已存在
        file_path = os.path.join(id_dir, filename)
        if os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': f'文件 {filename} 已存在，请使用不同的文件名'
            })
        
        # 读取并验证文件内容
        content = file.read().decode('utf-8')
        lines = content.split('\n')
        valid_lines = []
        invalid_count = 0
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            # 验证格式：邮箱----密码----电话----接码地址
            parts = line.split('----')
            if len(parts) == 4:
                # 检查每个字段是否不为空
                if all(part.strip() for part in parts):
                    valid_lines.append(line)
                else:
                    invalid_count += 1
                    logger.warning(f"第{i}行：字段为空")
            else:
                invalid_count += 1
                logger.warning(f"第{i}行：格式错误，期望4个字段，实际{len(parts)}个")
        
        if not valid_lines:
            return jsonify({
                'success': False,
                'message': '文件中没有有效的Apple ID数据，请检查格式'
            })
        
        # 保存文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(valid_lines))
        
        logger.info(f"Apple ID文件上传成功: {filename}, 有效行数: {len(valid_lines)}, 无效行数: {invalid_count}")
        
        return jsonify({
            'success': True,
            'message': f'文件上传成功！有效行数: {len(valid_lines)}',
            'filename': filename,
            'valid_lines': len(valid_lines),
            'invalid_lines': invalid_count
        })
        
    except Exception as e:
        logger.error(f"Apple ID文件上传失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'文件上传失败: {str(e)}'
        })

@app.route('/api/appleid_delete', methods=['POST'])
@login_required
def api_appleid_delete():
    """删除Apple ID数据"""
    logger.info("收到Apple ID删除请求")
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '未提供删除数据'
            })
        
        filename = data.get('file_name')
        line_index = data.get('line_index')
        original_line = data.get('original_line')
        
        if not filename or line_index is None or not original_line:
            return jsonify({
                'success': False,
                'message': '缺少必要的删除参数'
            })
        
        # 从配置文件读取目录路径
        from config import appleid_unused_dir, appleid_delete_dir
        file_path = os.path.join(project_root, appleid_unused_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': f'文件不存在: {filename}'
            })
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 确保行索引有效
        if line_index >= len(lines):
            return jsonify({
                'success': False,
                'message': f'行索引超出范围: {line_index}'
            })
        
        # 验证要删除的行
        target_line = lines[line_index].strip()
        if target_line != original_line:
            return jsonify({
                'success': False,
                'message': '要删除的行与原始行不匹配'
            })
        
        # 创建删除目录
        delete_dir = os.path.join(project_root, appleid_delete_dir)
        os.makedirs(delete_dir, exist_ok=True)
        
        # 创建删除备份文件
        backup_filename = f"{os.path.splitext(filename)[0]}_bak.txt"
        backup_path = os.path.join(delete_dir, backup_filename)
        
        # 将删除的行写入删除备份文件
        with open(backup_path, 'a', encoding='utf-8') as f:
            f.write(f"{original_line}\n")
        
        # 从原文件中删除该行
        lines.pop(line_index)
        
        # 写回原文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        logger.info(f"成功删除Apple ID数据，文件: {filename}, 行索引: {line_index}")
        
        return jsonify({
            'success': True,
            'message': '删除成功，数据已移动到删除备份文件'
        })
        
    except Exception as e:
        logger.error(f"删除Apple ID数据失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除失败: {str(e)}'
        })

@app.route('/api/apple_ids')
@login_required
def api_apple_ids():
    """获取Apple ID列表"""
    logger.info("收到获取Apple ID列表请求")
    try:
        apple_ids = []
        # 从配置文件读取目录路径
        from config import appleid_unused_dir
        id_dir = os.path.join(project_root, appleid_unused_dir)
        
        # 确保ID目录存在
        if not os.path.exists(id_dir):
            os.makedirs(id_dir, exist_ok=True)
            logger.info("创建ID_unused目录")
        
        # 查找ID目录下的所有.txt文件
        if os.path.exists(id_dir):
            for filename in os.listdir(id_dir):
                if filename.endswith('.txt'):
                    file_path = os.path.join(id_dir, filename)
                    
                    # 读取文件内容，尝试多种编码
                    content = ""
                    encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin-1']
                    
                    for encoding in encodings:
                        try:
                            with open(file_path, 'r', encoding=encoding) as f:
                                content = f.read().strip()
                            logger.info(f"成功使用 {encoding} 编码读取文件 {filename}")
                            break
                        except UnicodeDecodeError:
                            logger.warning(f"使用 {encoding} 编码读取文件 {filename} 失败，尝试下一种编码")
                            continue
                        except Exception as e:
                            logger.error(f"读取文件 {filename} 时发生错误: {str(e)}")
                            continue
                    
                    if content:
                        # 按行分割，过滤空行和无效行
                        lines = [line.strip() for line in content.split('\n') if line.strip()]
                        for line in lines:
                            # 提取Apple ID（邮箱部分，第一个----之前的内容）
                            if '----' in line:
                                apple_id = line.split('----')[0].strip()
                                if apple_id and '@' in apple_id:  # 确保是有效的邮箱格式
                                    apple_ids.append(apple_id)
                            else:
                                # 如果没有分隔符，直接使用整行作为Apple ID
                                if '@' in line:
                                    apple_ids.append(line)
                        logger.info(f"从文件 {filename} 中读取到 {len(lines)} 行，提取到 {len([l for l in lines if '----' in l])} 个Apple ID")
            
            # 按文件分组统计Apple ID
            file_apple_ids = {}
            for filename in os.listdir(id_dir):
                if filename.endswith('.txt'):
                    file_path = os.path.join(id_dir, filename)
                    
                    # 读取文件内容
                    content = ""
                    encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin-1']
                    
                    for encoding in encodings:
                        try:
                            with open(file_path, 'r', encoding=encoding) as f:
                                content = f.read().strip()
                            break
                        except UnicodeDecodeError:
                            continue
                        except Exception as e:
                            logger.error(f"读取文件 {filename} 时发生错误: {str(e)}")
                            continue
                    
                    if content:
                        # 统计该文件中的Apple ID数量
                        lines = [line.strip() for line in content.split('\n') if line.strip()]
                        apple_count = 0
                        for line in lines:
                            if '----' in line:
                                apple_id = line.split('----')[0].strip()
                                if apple_id and '@' in apple_id:
                                    apple_count += 1
                            elif '@' in line:
                                apple_count += 1
                        
                        if apple_count > 0:
                            file_apple_ids[filename] = apple_count
            
            # 转换为列表格式，显示文件名
            apple_id_list = []
            for filename, count in file_apple_ids.items():
                apple_id_list.append({
                    'id': filename,
                    'text': filename,  # 显示文件名
                    'display_text': f"{filename} (可用: {count})",  # 带数量信息的显示文本
                    'count': count
                })
            
            # 按文件名排序
            apple_id_list.sort(key=lambda x: x['id'])
            
            logger.info(f"总共找到 {len(apple_id_list)} 个唯一的Apple ID")
            
            return jsonify({
                'success': True,
                'apple_ids': apple_id_list
            })
        else:
            logger.warning("ID目录不存在")
            return jsonify({
                'success': True,
                'apple_ids': []
            })
        
    except Exception as e:
        logger.error(f"获取Apple ID列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取Apple ID列表失败: {str(e)}'
        })

@app.route('/api/batch_im_login', methods=['POST'])
@login_required
def api_batch_im_login():
    """批量IM登录"""
    logger.info("收到批量IM登录请求")
    try:
        data = request.get_json()
        vm_names = data.get('vm_names', [])
        apple_id_file = data.get('apple_id_file')
        
        if not vm_names:
            return jsonify({
                'success': False,
                'message': '请选择虚拟机'
            })
        
        if not apple_id_file:
            return jsonify({
                'success': False,
                'message': '请选择Apple ID文件'
            })
        
        # 验证虚拟机状态
        running_vms = []
        stopped_vms = []
        unknown_vms = []
        
        for vm_name in vm_names:
            try:
                vm_status = get_vm_online_status(vm_name)
                if vm_status['status'] == 'online' or vm_status['vm_status'] == 'running':
                    running_vms.append(vm_name)
                elif vm_status['status'] == 'offline' or vm_status['vm_status'] == 'stopped':
                    stopped_vms.append(vm_name)
                else:
                    unknown_vms.append(vm_name)
            except Exception as e:
                logger.error(f"检查虚拟机 {vm_name} 状态失败: {str(e)}")
                unknown_vms.append(vm_name)
        
        # 检查是否有非运行中的虚拟机
        if stopped_vms or unknown_vms:
            error_msg = "只能对运行中的虚拟机执行批量IM登录操作。"
            if stopped_vms:
                error_msg += f"\n已停止的虚拟机: {', '.join(stopped_vms)}"
            if unknown_vms:
                error_msg += f"\n状态未知的虚拟机: {', '.join(unknown_vms)}"
            
            return jsonify({
                'success': False,
                'message': error_msg
            })
        
        logger.info(f"批量IM登录验证通过 - 运行中虚拟机: {running_vms}, Apple ID文件: {apple_id_file}")
        
        # 读取Apple ID文件内容
        from config import appleid_unused_dir, appleidtxt_path, vm_username
        apple_id_file_path = os.path.join(project_root, appleid_unused_dir, apple_id_file)
        
        if not os.path.exists(apple_id_file_path):
            return jsonify({
                'success': False,
                'message': f'Apple ID文件不存在: {apple_id_file}'
            })
        
        # 读取文件内容，尝试多种编码
        content = ""
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin-1']
        used_encoding = None
        
        for encoding in encodings:
            try:
                with open(apple_id_file_path, 'r', encoding=encoding) as f:
                    content = f.read().strip()
                used_encoding = encoding
                logger.info(f"成功使用 {encoding} 编码读取文件 {apple_id_file}")
                break
            except UnicodeDecodeError:
                logger.warning(f"使用 {encoding} 编码读取文件 {apple_id_file} 失败，尝试下一种编码")
                continue
            except Exception as e:
                logger.error(f"读取文件 {apple_id_file} 时发生错误: {str(e)}")
                continue
        
        if not content:
            return jsonify({
                'success': False,
                'message': f'无法读取Apple ID文件 {apple_id_file}，请检查文件编码'
            })
        
        # 解析Apple ID内容
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        apple_ids = []
        for line in lines:
            if '----' in line:
                apple_id = line.split('----')[0].strip()
                if apple_id and '@' in apple_id:
                    apple_ids.append(line)  # 保留完整行
            else:
                if '@' in line:
                    apple_ids.append(line)
        
        if not apple_ids:
            return jsonify({
                'success': False,
                'message': f'Apple ID文件 {apple_id_file} 中没有找到有效的Apple ID'
            })
        
        logger.info(f"从文件 {apple_id_file} 中提取到 {len(apple_ids)} 个Apple ID")
        
        # 检查Apple ID数量是否足够分配给所有虚拟机
        if len(apple_ids) < len(running_vms):
            return jsonify({
                'success': False,
                'message': f'Apple ID数量不足，需要 {len(running_vms)} 个，但只有 {len(apple_ids)} 个可用'
            })
        
        # 每个虚拟机分配一个Apple ID
        apple_ids_per_vm = 1
        # 只使用前running_vms数量的Apple ID
        apple_ids_to_distribute = apple_ids[:len(running_vms)]
        
        logger.info(f"每个虚拟机分配 {apple_ids_per_vm} 个Apple ID，共使用 {len(apple_ids_to_distribute)} 个")
        
        # 使用多线程并发处理每个虚拟机的登录
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = []
        results_lock = threading.Lock()  # 用于保护results列表的线程安全
        
        def process_vm_login(vm_name, vm_index, apple_id_data):
            """处理单个虚拟机的登录过程"""
            vm_result = {
                'vm_name': vm_name,
                'success': False,
                'message': '',
                'apple_id_count': 1,
                'apple_id_range': f"{vm_index+1}",
                'script_executed': False,
                'script_message': ''
            }
            
            try:
                 logger.info(f"[线程] 开始处理虚拟机 {vm_name} 的登录")
                 
                 # 获取虚拟机IP
                 vm_ip = get_vm_ip(vm_name)
                 if not vm_ip:
                     vm_result['message'] = '无法获取虚拟机IP地址'
                     return vm_result
                
                # 获取分配给当前虚拟机的Apple ID（每个虚拟机一个）
                 vm_apple_ids = [apple_id_data]
                 
                 logger.info(f"[线程] 虚拟机 {vm_name} 分配第 {vm_index+1} 个Apple ID: {vm_apple_ids[0]}")
                 
                 # 创建临时文件
                 temp_file_name = f"{vm_name}_appleid.txt"
                 temp_file_path = os.path.join(project_root, 'temp', temp_file_name)
                 
                 # 确保临时目录存在
                 os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
                 
                 # 写入分配给当前虚拟机的Apple ID到临时文件
                 with open(temp_file_path, 'w', encoding='utf-8') as f:
                     f.write(vm_apple_ids[0])
                 
                 logger.info(f"[线程] 创建临时文件: {temp_file_path}，包含 1 个Apple ID")
                
                 # 直接传输文件，不校验远端目录是否存在
                 logger.info(f"[线程] 直接传输Apple ID文件到虚拟机 {vm_name}，不校验远端目录")
                 
                 # 使用SCP传输文件到虚拟机的Documents目录，文件名固定为appleid.txt
                 remote_file_path = f"{appleidtxt_path}appleid.txt"
                 
                 scp_cmd = [
                     'scp',
                     '-o', 'StrictHostKeyChecking=no',
                     temp_file_path,
                     f"{vm_username}@{vm_ip}:{remote_file_path}"
                 ]
                 
                 logger.info(f"[线程] 执行SCP命令: {' '.join(scp_cmd)}")
                 result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=60)
                
                 if result.returncode == 0:
                     logger.info(f"[线程] 成功传输Apple ID文件到虚拟机 {vm_name} 的Documents目录")
                     
                     # 执行登录脚本
                     script_success = False
                     script_message = ""
                    
                     try:
                         # 从config导入script_upload_dirs
                         from config import script_upload_dirs
                         
                         # 查找imessage_test.scpt脚本
                         script_found = False
                         script_path = None
                         
                         for script_dir in script_upload_dirs:
                             # 直接使用完整路径
                             potential_script_path = os.path.join(script_dir, 'imessage_test.scpt')
                             logger.info(f"[线程] 检查脚本路径: {potential_script_path}")
                             if os.path.exists(potential_script_path):
                                 script_path = potential_script_path
                                 script_found = True
                                 logger.info(f"[线程] 找到登录脚本: {script_path}")
                                 break
                             else:
                                 logger.warning(f"[线程] 脚本不存在: {potential_script_path}")
                        
                         if script_found:
                             # 先传输脚本到虚拟机，然后调用API执行
                             remote_script_path = f"{script_remote_path}imessage_test.scpt"
                             scp_script_cmd = [
                                 'scp',
                                 '-o', 'StrictHostKeyChecking=no',
                                 script_path,
                                 f"{vm_username}@{vm_ip}:{remote_script_path}"
                             ]
                             
                             logger.info(f"[线程] 传输登录脚本到虚拟机 {vm_name}: {' '.join(scp_script_cmd)}")
                             script_transfer_result = subprocess.run(scp_script_cmd, capture_output=True, text=True, timeout=60)
                             
                             if script_transfer_result.returncode == 0:
                                 logger.info(f"[线程] 成功传输登录脚本到虚拟机 {vm_name}")
                                
                                 # 调用客户端8787端口API执行登录脚本
                                 try:
                                     import requests
                                     
                                     script_api_url = f"http://{vm_ip}:8787/run?path={remote_script_path}"
                                     logger.info(f"[线程] 调用客户端API执行登录脚本: {script_api_url}")
                                     
                                     response = requests.get(script_api_url, timeout=300)
                                     
                                     if response.status_code == 200:
                                         script_output = response.text.strip()
                                         logger.info(f"[线程] 虚拟机 {vm_name} 登录脚本执行成功，输出: {script_output}")
                                         script_success = True
                                         script_message = f"登录脚本执行成功: {script_output}"
                                     else:
                                         logger.error(f"[线程] 虚拟机 {vm_name} 登录脚本执行失败，HTTP状态码: {response.status_code}")
                                         script_message = f"登录脚本执行失败: HTTP {response.status_code}"
                                        
                                 except requests.exceptions.Timeout:
                                     logger.error(f"[线程] 虚拟机 {vm_name} 登录脚本执行超时")
                                     script_message = "登录脚本执行超时"
                                 except requests.exceptions.ConnectionError:
                                     logger.error(f"[线程] 虚拟机 {vm_name} 无法连接到8787端口")
                                     script_message = "无法连接到客户端8787端口"
                                 except Exception as api_error:
                                     logger.error(f"[线程] 虚拟机 {vm_name} API调用异常: {str(api_error)}")
                                     script_message = f"API调用异常: {str(api_error)}"
                             else:
                                 script_error = script_transfer_result.stderr.strip() if script_transfer_result.stderr else '未知错误'
                                 logger.error(f"[线程] 传输登录脚本到虚拟机 {vm_name} 失败: {script_error}")
                                 script_message = f"登录脚本传输失败: {script_error}"
                         else:
                             logger.warning(f"[线程] 未找到imessage_test.scpt登录脚本")
                             script_message = "未找到登录脚本"
                            
                     except Exception as e:
                         logger.error(f"[线程] 执行登录脚本时发生错误: {str(e)}")
                         script_message = f"脚本执行异常: {str(e)}"
                     
                     # 组合结果消息
                     final_message = f'appleid.txt文件已成功传输到虚拟机 {vm_name} 的Documents目录'
                     if script_message:
                         final_message += f'; {script_message}'
                     
                     # 使用线程锁保护共享资源
                     with results_lock:
                         results.append({
                             'vm_name': vm_name,
                             'success': True,
                             'message': final_message,
                             'remote_path': remote_file_path,
                             'apple_id_count': len(vm_apple_ids),
                             'apple_id_range': f"{i+1}",
                             'script_executed': script_success,
                             'script_message': script_message
                         })
                 else:
                     error_msg = result.stderr.strip() if result.stderr else '未知错误'
                     logger.error(f"[线程] 传输Apple ID文件到虚拟机 {vm_name} 失败: {error_msg}")
                     with results_lock:
                         results.append({
                             'vm_name': vm_name,
                             'success': False,
                             'message': f'传输失败: {error_msg}',
                             'apple_id_count': len(vm_apple_ids),
                             'apple_id_range': f"{i+1}"
                         })
                
                 # 清理临时文件
                 try:
                     os.remove(temp_file_path)
                     logger.info(f"[线程] 清理临时文件: {temp_file_path}")
                 except Exception as e:
                     logger.warning(f"[线程] 清理临时文件失败: {str(e)}")
                
            except subprocess.TimeoutExpired:
                logger.error(f"[线程] 传输Apple ID文件到虚拟机 {vm_name} 超时")
                with results_lock:
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': '传输超时（60秒）'
                    })
            except Exception as e:
                logger.error(f"[线程] 处理虚拟机 {vm_name} 时发生错误: {str(e)}")
                with results_lock:
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': f'处理失败: {str(e)}'
                    })
        
        # 使用线程池并发执行虚拟机登录任务
        with ThreadPoolExecutor(max_workers=min(len(running_vms), 10)) as executor:
            # 提交所有任务
            futures = []
            for i, vm_name in enumerate(running_vms):
                future = executor.submit(process_vm_login, vm_name, i, apple_ids_to_distribute[i])
                futures.append(future)
            
            # 等待所有任务完成
            for future in as_completed(futures):
                try:
                    future.result()  # 获取结果，如果有异常会抛出
                except Exception as e:
                    logger.error(f"线程执行异常: {str(e)}")
        
        # 统计结果
        success_count = sum(1 for r in results if r['success'])
        total_count = len(results)
        
        # 计算分配的Apple ID总数
        total_allocated = sum(r.get('apple_id_count', 0) for r in results if r['success'])
        
        # 统计脚本执行结果
        script_success_count = sum(1 for r in results if r.get('script_executed', False))
        script_total_count = sum(1 for r in results if r['success'])  # 只统计文件传输成功的虚拟机
        
        # 如果有成功的分发，则标记Apple ID为已使用
        used_apple_ids = []
        if success_count > 0:
            try:
                from config import appleid_install_dir
                
                # 获取已使用的Apple ID
                for i, result in enumerate(results):
                    if result['success']:
                        used_apple_ids.append(apple_ids_to_distribute[i])
                
                if used_apple_ids:
                    # 创建备份文件到ID_install目录
                    backup_file_name = f"{apple_id_file.replace('.txt', '')}_bak.txt"
                    backup_file_path = os.path.join(project_root, appleid_install_dir, backup_file_name)
                    
                    # 确保目录存在
                    os.makedirs(os.path.dirname(backup_file_path), exist_ok=True)
                    
                    # 增量写入已使用的Apple ID到备份文件
                    try:
                        # 读取现有备份文件内容（如果存在）
                        existing_backup_ids = []
                        if os.path.exists(backup_file_path):
                            try:
                                with open(backup_file_path, 'r', encoding='utf-8') as f:
                                    existing_content = f.read().strip()
                                    if existing_content:
                                        existing_backup_ids = existing_content.split('\n')
                                logger.info(f"读取现有备份文件，包含 {len(existing_backup_ids)} 个Apple ID")
                            except UnicodeDecodeError:
                                # 如果UTF-8解码失败，尝试其他编码
                                for encoding in ['gbk', 'gb2312', 'latin-1']:
                                    try:
                                        with open(backup_file_path, 'r', encoding=encoding) as f:
                                            existing_content = f.read().strip()
                                            if existing_content:
                                                existing_backup_ids = existing_content.split('\n')
                                        logger.info(f"使用 {encoding} 编码读取现有备份文件，包含 {len(existing_backup_ids)} 个Apple ID")
                                        break
                                    except UnicodeDecodeError:
                                        continue
                        
                        # 合并现有和新使用的Apple ID，去重
                        all_backup_ids = existing_backup_ids + used_apple_ids
                        unique_backup_ids = list(dict.fromkeys(all_backup_ids))  # 保持顺序的去重
                        
                        # 增量写入备份文件（使用UTF-8编码）
                        with open(backup_file_path, 'w', encoding='utf-8') as f:
                            f.write('\n'.join(unique_backup_ids))
                        
                        logger.info(f"已使用的Apple ID已增量备份到: {backup_file_path}")
                        logger.info(f"备份文件总计包含 {len(unique_backup_ids)} 个Apple ID（新增 {len(used_apple_ids)} 个）")
                        
                    except Exception as e:
                        logger.error(f"备份文件操作失败: {str(e)}")
                        # 如果备份失败，仍然继续处理原文件
                    
                    # 从原文件中移除已使用的Apple ID
                    remaining_apple_ids = [aid for aid in apple_ids if aid not in used_apple_ids]
                    
                    # 更新原文件（使用检测到的编码，如果没有检测到则使用UTF-8）
                    try:
                        write_encoding = used_encoding if used_encoding else 'utf-8'
                        with open(apple_id_file_path, 'w', encoding=write_encoding) as f:
                            f.write('\n'.join(remaining_apple_ids))
                        
                        logger.info(f"已从原文件中移除 {len(used_apple_ids)} 个已使用的Apple ID（使用 {write_encoding} 编码）")
                        
                    except Exception as e:
                        logger.error(f"更新原文件失败: {str(e)}")
                        # 如果更新原文件失败，记录错误但不影响整体流程
                    
            except Exception as e:
                logger.error(f"标记Apple ID为已使用时发生错误: {str(e)}")
        
        # 构建完整的结果消息
        result_message = f'批量IM登录任务完成，appleid.txt文件已成功传输到 {success_count}/{total_count} 个虚拟机的Documents目录，共分配 {total_allocated} 个Apple ID'
        if script_total_count > 0:
            result_message += f'，登录脚本执行成功 {script_success_count}/{script_total_count} 个虚拟机'
        
        return jsonify({
            'success': True,
            'message': result_message,
            'results': results,
            'summary': {
                'total_vms': total_count,
                'success_count': success_count,
                'failed_count': total_count - success_count,
                'total_apple_ids': len(apple_ids),
                'allocated_apple_ids': total_allocated,
                'used_apple_ids': len(used_apple_ids),
                'source_file': apple_id_file,
                'backup_file': backup_file_name if used_apple_ids else None,
                'script_execution': {
                    'script_success_count': script_success_count,
                    'script_total_count': script_total_count,
                    'script_success_rate': f'{script_success_count}/{script_total_count}' if script_total_count > 0 else '0/0'
                },
                'distribution_info': {
                    'apple_ids_per_vm': apple_ids_per_vm,
                    'total_apple_ids_used': len(apple_ids_to_distribute),
                    'distribution_method': 'one_apple_id_per_vm'
                }
            }
        })
        
    except Exception as e:
        logger.error(f"批量IM登录失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量IM登录失败: {str(e)}'
        })

@app.route('/api/appleid_stats')
@login_required
def api_appleid_stats():
    """获取Apple ID统计信息"""
    logger.info("收到Apple ID统计信息请求")
    try:
        from config import appleid_unused_dir, appleid_install_dir, appleid_delete_dir
        
        # 获取请求参数中的文件名
        filename = request.args.get('filename', 'test.txt')
        logger.info(f"统计文件名: {filename}")
        
        # 计算可用ID数量（有效Apple ID = 可用ID，从未使用目录中的下拉文件名读取）
        available_count = 0
        unused_dir = os.path.join(project_root, appleid_unused_dir)
        file_path = os.path.join(unused_dir, filename)
        if os.path.exists(file_path):
            content = ""
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin-1']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read().strip()
                    logger.info(f"成功使用 {encoding} 编码读取文件 {filename}")
                    break
                except UnicodeDecodeError:
                    logger.warning(f"使用 {encoding} 编码读取文件 {filename} 失败，尝试下一种编码")
                    continue
                except Exception as e:
                    logger.error(f"读取文件 {filename} 时发生错误: {str(e)}")
                    continue
            
            if content:
                lines = content.split('\n') if content else []
                for line in lines:
                    if line.strip() and '----' in line:
                        parts = line.split('----')
                        if len(parts) >= 4:
                            available_count += 1
            else:
                logger.warning(f"无法读取{filename}文件，编码问题")
        
        # 计算已使用ID数量（已安装目录中的下拉文件名加_bak文件）
        used_count = 0
        install_dir = os.path.join(project_root, appleid_install_dir)
        # 从文件名中提取基础名称（去掉.txt后缀）
        base_filename = filename.replace('.txt', '')
        bak_filename = f"{base_filename}_bak.txt"
        bak_file_path = os.path.join(install_dir, bak_filename)
        if os.path.exists(bak_file_path):
            content = ""
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin-1']
            
            for encoding in encodings:
                try:
                    with open(bak_file_path, 'r', encoding=encoding) as f:
                        content = f.read().strip()
                    logger.info(f"成功使用 {encoding} 编码读取文件 {bak_filename}")
                    break
                except UnicodeDecodeError:
                    logger.warning(f"使用 {encoding} 编码读取文件 {bak_filename} 失败，尝试下一种编码")
                    continue
                except Exception as e:
                    logger.error(f"读取文件 {bak_filename} 时发生错误: {str(e)}")
                    continue
            
            if content:
                lines = content.split('\n') if content else []
                for line in lines:
                    if line.strip() and '----' in line:
                        parts = line.split('----')
                        if len(parts) >= 4:
                            used_count += 1
            else:
                logger.warning(f"无法读取{bak_filename}文件，编码问题")
        
        # 计算无效ID数量（删除目录中的下拉文件名加_bak文件）
        invalid_count = 0
        delete_dir = os.path.join(project_root, appleid_delete_dir)
        bak_file_path = os.path.join(delete_dir, bak_filename)
        if os.path.exists(bak_file_path):
            content = ""
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin-1']
            
            for encoding in encodings:
                try:
                    with open(bak_file_path, 'r', encoding=encoding) as f:
                        content = f.read().strip()
                    logger.info(f"成功使用 {encoding} 编码读取文件 {bak_filename}")
                    break
                except UnicodeDecodeError:
                    logger.warning(f"使用 {encoding} 编码读取文件 {bak_filename} 失败，尝试下一种编码")
                    continue
                except Exception as e:
                    logger.error(f"读取文件 {bak_filename} 时发生错误: {str(e)}")
                    continue
            
            if content:
                lines = content.split('\n') if content else []
                for line in lines:
                    if line.strip() and '----' in line:
                        parts = line.split('----')
                        if len(parts) >= 4:
                            invalid_count += 1
            else:
                logger.warning(f"无法读取{bak_filename}文件，编码问题")
        
        # 计算总数量：总ID数量 = 无效ID + 可用ID + 已使用ID
        total_count = invalid_count + available_count + used_count
        
        logger.info(f"Apple ID统计信息 - 文件: {filename}, 可用ID(有效): {available_count}, 已使用: {used_count}, 无效: {invalid_count}, 总计: {total_count}")
        
        return jsonify({
            'success': True,
            'stats': {
                'total': total_count,
                'valid': available_count,  # 有效Apple ID = 可用ID
                'used': used_count,
                'invalid': invalid_count
            }
        })
        
    except Exception as e:
        logger.error(f"获取Apple ID统计信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取统计信息失败: {str(e)}'
        })

@app.route('/api/distribute_text_lines', methods=['POST'])
@login_required
def api_distribute_text_lines():
    """将多行文本分别分发到多个虚拟机"""
    logger.info("收到多行文本分发请求")
    try:
        data = request.get_json()
        vm_names = data.get('vm_names', [])
        text_lines = data.get('text_lines', [])  # 多行文本内容
        file_name = data.get('file_name', 'distributed_text.txt')  # 远程文件名
        remote_path = data.get('remote_path', None)  # 远程路径，如果为None则使用默认路径
        
        if not vm_names:
            return jsonify({
                'success': False,
                'message': '请选择虚拟机'
            })
        
        if not text_lines:
            return jsonify({
                'success': False,
                'message': '请提供要分发的文本内容'
            })
        
        # 验证虚拟机状态
        running_vms = []
        stopped_vms = []
        unknown_vms = []
        
        for vm_name in vm_names:
            try:
                vm_status = get_vm_online_status(vm_name)
                if vm_status['status'] == 'online' or vm_status['vm_status'] == 'running':
                    running_vms.append(vm_name)
                elif vm_status['status'] == 'offline' or vm_status['vm_status'] == 'stopped':
                    stopped_vms.append(vm_name)
                else:
                    unknown_vms.append(vm_name)
            except Exception as e:
                logger.error(f"检查虚拟机 {vm_name} 状态失败: {str(e)}")
                unknown_vms.append(vm_name)
        
        # 检查是否有非运行中的虚拟机
        if stopped_vms or unknown_vms:
            error_msg = "只能对运行中的虚拟机执行文本分发操作。"
            if stopped_vms:
                error_msg += f"\n已停止的虚拟机: {', '.join(stopped_vms)}"
            if unknown_vms:
                error_msg += f"\n状态未知的虚拟机: {', '.join(unknown_vms)}"
            
            return jsonify({
                'success': False,
                'message': error_msg
            })
        
        logger.info(f"文本分发验证通过 - 运行中虚拟机: {running_vms}, 文本行数: {len(text_lines)}")
        
        # 检查文本行数是否足够分配给所有虚拟机
        if len(text_lines) < len(running_vms):
            return jsonify({
                'success': False,
                'message': f'文本行数不足，需要 {len(running_vms)} 行，但只有 {len(text_lines)} 行可用'
            })
        
        # 每个虚拟机分配一行文本
        lines_per_vm = 1
        # 只使用前running_vms数量的行
        text_lines_to_distribute = text_lines[:len(running_vms)]
        
        logger.info(f"每个虚拟机分配 {lines_per_vm} 行文本，共使用 {len(text_lines_to_distribute)} 行")
        
        # 为每个虚拟机创建临时文件并传输
        results = []
        start_index = 0
        
        for i, vm_name in enumerate(running_vms):
            try:
                # 获取虚拟机IP
                vm_ip = get_vm_ip(vm_name)
                if not vm_ip:
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': '无法获取虚拟机IP地址'
                    })
                    continue
                
                # 获取分配给当前虚拟机的文本行（每个虚拟机一行）
                vm_text_lines = [text_lines_to_distribute[i]]
                
                logger.info(f"虚拟机 {vm_name} 分配第 {i+1} 行文本: {vm_text_lines[0]}")
                
                # 创建临时文件
                temp_file_name = f"{vm_name}_{file_name}"
                temp_file_path = os.path.join(project_root, 'temp', temp_file_name)
                
                # 确保临时目录存在
                os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
                
                # 写入分配给当前虚拟机的文本行到临时文件
                with open(temp_file_path, 'w', encoding='utf-8') as f:
                    f.write(vm_text_lines[0])
                
                logger.info(f"创建临时文件: {temp_file_path}，包含 1 行文本")
                
                # 确定远程文件路径
                if remote_path:
                    remote_file_path = f"{remote_path}/{file_name}"
                else:
                    remote_file_path = f"/Users/{vm_username}/{file_name}"
                
                # 使用SCP传输文件到虚拟机
                scp_cmd = [
                    'scp',
                    '-o', 'StrictHostKeyChecking=no',
                    temp_file_path,
                    f"{vm_username}@{vm_ip}:{remote_file_path}"
                ]
                
                logger.info(f"执行SCP命令: {' '.join(scp_cmd)}")
                result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    logger.info(f"成功传输文本文件到虚拟机 {vm_name}")
                    results.append({
                        'vm_name': vm_name,
                        'success': True,
                        'message': f'文本文件已成功传输到虚拟机 {vm_name}',
                        'remote_path': remote_file_path,
                        'line_count': len(vm_text_lines),
                        'line_range': f"{i+1}",
                        'text_lines': vm_text_lines  # 返回分配给该虚拟机的具体文本行
                    })
                else:
                    error_msg = result.stderr.strip() if result.stderr else '未知错误'
                    logger.error(f"传输文本文件到虚拟机 {vm_name} 失败: {error_msg}")
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': f'传输失败: {error_msg}',
                        'line_count': len(vm_text_lines),
                        'line_range': f"{i+1}"
                    })
                
                # 清理临时文件
                try:
                    os.remove(temp_file_path)
                    logger.info(f"清理临时文件: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {str(e)}")
                
            except subprocess.TimeoutExpired:
                logger.error(f"传输文本文件到虚拟机 {vm_name} 超时")
                results.append({
                    'vm_name': vm_name,
                    'success': False,
                    'message': '传输超时（60秒）'
                })
            except Exception as e:
                logger.error(f"处理虚拟机 {vm_name} 时发生错误: {str(e)}")
                results.append({
                    'vm_name': vm_name,
                    'success': False,
                    'message': f'处理失败: {str(e)}'
                })
        
        # 统计结果
        success_count = sum(1 for r in results if r['success'])
        total_count = len(results)
        
        # 计算分配的文本行总数
        total_allocated = sum(r.get('line_count', 0) for r in results if r['success'])
        
        return jsonify({
            'success': True,
            'message': f'文本分发任务完成，成功传输到 {success_count}/{total_count} 个虚拟机，共分配 {total_allocated} 行文本',
            'results': results,
            'summary': {
                'total_vms': total_count,
                'success_count': success_count,
                'failed_count': total_count - success_count,
                'total_text_lines': len(text_lines),
                'allocated_lines': total_allocated,
                'file_name': file_name,
                'distribution_info': {
                    'lines_per_vm': lines_per_vm,
                    'total_lines_used': len(text_lines_to_distribute),
                    'distribution_method': 'one_line_per_vm'
                }
            }
        })
        
    except Exception as e:
        logger.error(f"文本分发失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'文本分发失败: {str(e)}'
        })

# 客户端管理相关API
@app.route('/api/scan_clients', methods=['POST'])
@login_required
def api_scan_clients():
    """扫描ScptRunner客户端"""
    import socket
    import requests
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import ipaddress
    import re
    
    try:
        logger.info("开始扫描ScptRunner客户端")
        
        # 获取运行中虚拟机的IP地址
        def get_running_vm_ips():
            """只获取运行中虚拟机的IP地址，提高扫描效率"""
            vm_ips = []
            vmrun_path = get_vmrun_path()
            
            try:
                # 首先获取运行中的虚拟机列表
                list_cmd = [vmrun_path, 'list']
                result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    logger.error(f"获取运行中虚拟机列表失败: {result.stderr}")
                    return vm_ips
                
                running_vms = []
                lines = result.stdout.strip().split('\n')
                
                # 解析vmrun list输出
                for line in lines[1:]:  # 跳过第一行（Total running VMs: X）
                    line = line.strip()
                    if line and os.path.exists(line) and line.endswith('.vmx'):
                        running_vms.append(line)
                
                logger.info(f"发现 {len(running_vms)} 个运行中的虚拟机")
                
                # 只对运行中的虚拟机获取IP地址
                for vm_path in running_vms:
                    try:
                        vm_name = os.path.splitext(os.path.basename(vm_path))[0]
                        
                        # 使用vmrun获取虚拟机IP
                        command = f'"{vmrun_path}" getGuestIPAddress "{vm_path}"'
                        ip_result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
                        
                        if ip_result.returncode == 0:
                            ip = ip_result.stdout.strip()
                            # 验证IP地址格式
                            try:
                                ipaddress.ip_address(ip)
                                vm_ips.append({
                                    'ip': ip,
                                    'vm_name': vm_name,
                                    'vm_path': vm_path
                                })
                                logger.debug(f"获取到运行中虚拟机IP: {ip} ({vm_name})")
                            except ValueError:
                                logger.debug(f"虚拟机 {vm_name} 返回无效IP地址: {ip}")
                        else:
                            logger.debug(f"获取虚拟机 {vm_name} IP失败: {ip_result.stderr}")
                            
                    except Exception as e:
                        logger.debug(f"处理虚拟机 {vm_path} 失败: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"获取运行中虚拟机列表失败: {str(e)}")
            
            return vm_ips
        
        # 检查端口是否开放
        def check_port_open(ip, port, timeout=3):
            """检查指定IP的端口是否开放"""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, port))
                sock.close()
                return result == 0
            except Exception:
                return False
        
        # 获取ScptRunner客户端信息
        def get_scptrunner_info(ip, port=8787):
            """获取ScptRunner客户端信息"""
            try:
                # 尝试连接ScptRunner API获取版本信息
                url = f"http://{ip}:{port}/api/version"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'version': data.get('version', '未知版本'),
                        'details': data.get('details', 'ScptRunner客户端'),
                        'status': 'online'
                    }
                else:
                    # 如果API不可用，但端口开放，说明是ScptRunner但版本较老
                    return {
                        'version': '1.0.x',
                        'details': 'ScptRunner客户端 (旧版本)',
                        'status': 'online'
                    }
            except Exception:
                # 端口开放但无法获取版本信息
                return {
                    'version': '未知',
                    'details': 'ScptRunner客户端 (无法获取详细信息)',
                    'status': 'unknown'
                }
        
        # 扫描单个IP
        def scan_ip(vm_info):
            """扫描单个虚拟机IP的8787端口"""
            ip = vm_info['ip']
            vm_name = vm_info['vm_name']
            
            try:
                # 检查8787端口是否开放
                if check_port_open(ip, 8787):
                    # 获取ScptRunner信息
                    client_info = get_scptrunner_info(ip)
                    
                    return {
                        'id': f"client_{ip.replace('.', '_')}",
                        'version': client_info['version'],
                        'ip': ip,
                        'details': f"{client_info['details']}",
                        'status': client_info['status'],
                        'last_seen': datetime.now().isoformat(),
                        'vm_name': vm_name
                    }
                else:
                    return None
            except Exception as e:
                logger.debug(f"扫描IP {ip} 失败: {str(e)}")
                return None
        
        # 获取运行中虚拟机的IP
        logger.info("正在获取运行中虚拟机的IP地址...")
        vm_ips = get_running_vm_ips()
        logger.info(f"找到 {len(vm_ips)} 个运行中虚拟机的IP地址")
        
        if not vm_ips:
            return jsonify({
                'success': True,
                'message': '未找到运行中的虚拟机',
                'clients': []
            })
        
        # 并发扫描所有IP的8787端口
        logger.info("正在扫描8787端口...")
        discovered_clients = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            # 提交所有扫描任务
            future_to_ip = {executor.submit(scan_ip, vm_info): vm_info for vm_info in vm_ips}
            
            # 收集结果
            for future in as_completed(future_to_ip):
                vm_info = future_to_ip[future]
                try:
                    result = future.result()
                    if result:
                        discovered_clients.append(result)
                        logger.info(f"发现ScptRunner客户端: {result['ip']} (版本: {result['version']})")
                except Exception as e:
                    logger.error(f"扫描虚拟机 {vm_info['vm_name']} 失败: {str(e)}")
        
        # 按IP地址排序
        discovered_clients.sort(key=lambda x: ipaddress.ip_address(x['ip']))
        
        logger.info(f"扫描完成，发现 {len(discovered_clients)} 个ScptRunner客户端")
        
        return jsonify({
            'success': True,
            'message': f'成功扫描到 {len(discovered_clients)} 个ScptRunner客户端',
            'clients': discovered_clients,
            'scan_info': {
                'total_vms_scanned': len(vm_ips),
                'clients_found': len(discovered_clients),
                'scan_time': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"扫描客户端失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'扫描失败: {str(e)}'
        })

@app.route('/api/test_api', methods=['POST'])
@login_required
def api_test_api():
    """测试API功能"""
    try:
        data = request.get_json()
        api_content = data.get('api_content', '')
        
        if not api_content:
            return jsonify({
                'success': False,
                'message': 'API内容不能为空'
            })
        
        logger.info(f"执行API测试: {api_content}")
        
        # 这里可以根据实际需求实现API测试逻辑
        # 例如：解析API内容、执行相应的操作等
        
        # 模拟API测试结果
        test_result = {
            'input': api_content,
            'timestamp': datetime.now().isoformat(),
            'status': 'success',
            'response': f'API测试成功，输入内容: {api_content}',
            'execution_time': '0.05s'
        }
        
        logger.info("API测试执行成功")
        
        return jsonify({
            'success': True,
            'message': 'API测试执行成功',
            'result': test_result
        })
        
    except Exception as e:
        logger.error(f"API测试失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'API测试失败: {str(e)}'
        })

@app.route('/api/test_url', methods=['POST'])
@login_required
def api_test_url():
    """测试URL GET请求功能"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({
                'success': False,
                'message': 'URL地址不能为空'
            })
        
        logger.info(f"执行URL GET请求测试: {url}")
        
        # 验证URL格式
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return jsonify({
                    'success': False,
                    'message': 'URL格式无效，请输入完整的URL地址'
                })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'URL格式验证失败: {str(e)}'
            })
        
        # 发送GET请求
        import requests
        start_time = time.time()
        
        try:
            # 设置请求超时时间为60秒，等待ScptRunner脚本执行完成
            response = requests.get(url, timeout=60)
            end_time = time.time()
            response_time = int((end_time - start_time) * 1000)  # 转换为毫秒
            
            # 获取响应内容
            try:
                # 尝试解析JSON响应
                response_json = response.json()
                response_text = json.dumps(response_json, indent=2, ensure_ascii=False)
            except:
                # 如果不是JSON，直接获取文本内容
                response_text = response.text
            
            # 限制响应内容长度，避免过长的响应
            if len(response_text) > 2000:
                response_text = response_text[:2000] + "\n\n... (响应内容过长，已截断)"
            
            logger.info(f"URL请求成功: {url}, 状态码: {response.status_code}, 响应时间: {response_time}ms")
            
            return jsonify({
                'success': True,
                'message': 'GET请求执行成功',
                'status_code': response.status_code,
                'response_time': response_time,
                'response_text': response_text,
                'headers': dict(response.headers),
                'url': url
            })
            
        except requests.exceptions.Timeout:
            logger.warning(f"URL请求超时: {url}")
            return jsonify({
                'success': False,
                'message': '请求超时（60秒），请检查URL地址是否可访问或脚本执行时间过长'
            })
            
        except requests.exceptions.ConnectionError:
            logger.warning(f"URL连接失败: {url}")
            return jsonify({
                'success': False,
                'message': '连接失败，请检查URL地址和网络连接'
            })
            
        except requests.exceptions.RequestException as e:
            logger.error(f"URL请求异常: {url}, 错误: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'请求失败: {str(e)}'
            })
        
    except Exception as e:
        logger.error(f"URL测试失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'测试过程中发生错误: {str(e)}'
        })

@app.route('/api/upgrade_client', methods=['POST'])
@login_required
def api_upgrade_client():
    """升级客户端"""
    try:
        data = request.get_json()
        client_id = data.get('client_id', '')
        
        if not client_id:
            return jsonify({
                'success': False,
                'message': '客户端ID不能为空'
            })
        
        logger.info(f"开始升级客户端: {client_id}")
        
        # 这里可以根据实际需求实现客户端升级逻辑
        # 例如：下载新版本、传输升级文件、执行升级脚本等
        
        # 模拟升级过程
        time.sleep(1)  # 模拟升级耗时
        
        logger.info(f"客户端 {client_id} 升级成功")
        
        return jsonify({
            'success': True,
            'message': f'客户端 {client_id} 升级成功'
        })
        
    except Exception as e:
        logger.error(f"客户端升级失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'升级失败: {str(e)}'
        })

@app.route('/api/delete_client', methods=['POST'])
@login_required
def api_delete_client():
    """删除客户端"""
    try:
        data = request.get_json()
        client_id = data.get('client_id', '')
        
        if not client_id:
            return jsonify({
                'success': False,
                'message': '客户端ID不能为空'
            })
        
        logger.info(f"开始删除客户端: {client_id}")
        
        # 这里可以根据实际需求实现客户端删除逻辑
        # 例如：清理客户端文件、移除注册信息等
        
        # 模拟删除过程
        time.sleep(0.5)  # 模拟删除耗时
        
        logger.info(f"客户端 {client_id} 删除成功")
        
        return jsonify({
            'success': True,
            'message': f'客户端 {client_id} 删除成功'
        })
        
    except Exception as e:
        logger.error(f"客户端删除失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除失败: {str(e)}'
        })

@app.route('/api/execute_im_test', methods=['POST'])
@login_required
def api_execute_im_test():
    """执行IM测试脚本"""
    try:
        data = request.get_json()
        client_id = data.get('client_id', '')
        script_name = data.get('script_name', 'imessage_test.scpt')
        
        if not client_id:
            return jsonify({
                'success': False,
                'message': '客户端ID不能为空'
            })
        
        logger.info(f"开始执行IM测试: 客户端ID={client_id}, 脚本={script_name}")
        
        # 从客户端ID中提取IP地址
        # 客户端ID格式通常为 "client_192_168_119_156"
        try:
            ip_parts = client_id.replace('client_', '').split('_')
            if len(ip_parts) == 4:
                client_ip = '.'.join(ip_parts)
            else:
                return jsonify({
                    'success': False,
                    'message': f'无效的客户端ID格式: {client_id}'
                })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'解析客户端IP失败: {str(e)}'
            })
        
        logger.info(f"解析得到客户端IP: {client_ip}")
        
        # 检查客户端是否在线（检查8787端口）
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((client_ip, 8787))
            sock.close()
            
            if result != 0:
                return jsonify({
                    'success': False,
                    'message': f'客户端 {client_ip} 不在线或8787端口未开放'
                })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'检查客户端连接失败: {str(e)}'
            })
        
        # 通过ScptRunner API执行脚本
        import requests
        try:
            # 构建ScptRunner API URL - 使用GET请求和查询参数格式
            scptrunner_url = f"http://{client_ip}:8787/script?name={script_name}"
            
            logger.info(f"调用ScptRunner API: {scptrunner_url}")
            logger.debug(f"脚本名称: {script_name}")
            
            # 发送GET请求到ScptRunner
            response = requests.get(
                scptrunner_url, 
                timeout=120  # 120秒超时，IM测试需要更多时间进行UI交互
            )
            
            if response.status_code == 200:
                # ScptRunner的GET请求通常直接返回脚本执行结果
                output = response.text
                logger.info(f"IM测试脚本执行成功，输出长度: {len(output)}")
                
                return jsonify({
                    'success': True,
                    'message': 'IM测试脚本执行成功',
                    'output': output,
                    'client_ip': client_ip,
                    'script_name': script_name
                })
            else:
                logger.error(f"ScptRunner API调用失败，状态码: {response.status_code}")
                error_text = response.text if response.text else '无响应内容'
                return jsonify({
                    'success': False,
                    'message': f'ScptRunner API调用失败，状态码: {response.status_code}',
                    'output': error_text,
                    'client_ip': client_ip
                })
                
        except requests.exceptions.Timeout:
            logger.warning(f"ScptRunner API调用超时: {client_ip}")
            return jsonify({
                'success': False,
                'message': 'IM测试脚本执行超时（120秒），请检查脚本是否正常运行或UI元素查找是否失败',
                'client_ip': client_ip
            })
            
        except requests.exceptions.ConnectionError:
            logger.error(f"无法连接到ScptRunner: {client_ip}")
            return jsonify({
                'success': False,
                'message': f'无法连接到ScptRunner客户端 {client_ip}:8787',
                'client_ip': client_ip
            })
            
        except Exception as e:
            logger.error(f"调用ScptRunner API异常: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'调用ScptRunner API失败: {str(e)}',
                'client_ip': client_ip
            })
        
    except Exception as e:
        logger.error(f"执行IM测试失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'执行IM测试失败: {str(e)}'
        })

# 手机号管理相关API
@app.route('/api/phone_config_list')
def get_phone_config_list():
    """获取手机号配置文件列表"""
    try:
        phone_unused_path = os.path.join(os.getcwd(), phone_unused_dir)
        configs = []
        
        if os.path.exists(phone_unused_path):
            for file in os.listdir(phone_unused_path):
                if file.endswith('.txt'):
                    file_path = os.path.join(phone_unused_path, file)
                    configs.append({
                        'name': file,
                        'is_default': file == 'default.txt'
                    })
        
        return jsonify({
            'success': True,
            'configs': configs
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/api/phone_list')
def get_phone_list():
    """获取手机号列表"""
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 5))
        config = request.args.get('config', 'default.txt')
        # 如果config为空字符串，使用默认值
        if not config or config.strip() == '':
            config = 'default.txt'
        
        phone_unused_path = os.path.join(os.getcwd(), phone_unused_dir)
        phone_delete_path = os.path.join(os.getcwd(), phone_delete_dir)
        
        phones = []
        active_count = 0
        deleted_count = 0
        used_count = 0
        
        # 读取有效手机号
        unused_file = os.path.join(phone_unused_path, config)
        if os.path.exists(unused_file):
            with open(unused_file, 'r', encoding='utf-8') as f:
                for line in f:
                    phone = line.strip()
                    if phone:
                        phones.append({
                            'number': phone,
                            'status': 'active',
                            'add_time': '未知'
                        })
                        active_count += 1
        
        # 读取已删除手机号（从_bak文件中读取）
        config_name = config.replace('.txt', '')
        bak_file = os.path.join(phone_delete_path, f"{config_name}_bak.txt")
        if os.path.exists(bak_file):
            with open(bak_file, 'r', encoding='utf-8') as f:
                for line in f:
                    phone = line.strip()
                    if phone:
                        phones.append({
                            'number': phone,
                            'status': 'deleted',
                            'add_time': '未知'
                        })
                        deleted_count += 1
        
        # 读取已使用手机号（从已删除文件中读取）
        delete_file = os.path.join(phone_delete_path, config)
        if os.path.exists(delete_file):
            with open(delete_file, 'r', encoding='utf-8') as f:
                for line in f:
                    phone = line.strip()
                    if phone:
                        phones.append({
                            'number': phone,
                            'status': 'used',
                            'add_time': '未知'
                        })
                        used_count += 1
        
        # 分页处理
        total_records = len(phones)
        start = (page - 1) * size
        end = start + size
        page_phones = phones[start:end]
        
        return jsonify({
            'success': True,
            'phones': page_phones,
            'total': active_count,  # 总手机号数 = 有效手机号数
            'active': active_count,  # 有效手机号数
            'deleted': deleted_count,  # 已删除数量（从_bak文件读取）
            'used': used_count,  # 已使用数量
            'page': page,
            'size': size,
            'total_records': total_records  # 用于分页的总记录数
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/api/upload_phone_file', methods=['POST'])
def upload_phone_file():
    """上传手机号文件"""
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
        
        # 检查文件格式
        allowed_extensions = ['.txt', '.csv']
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in allowed_extensions:
            return jsonify({
                'success': False,
                'message': '只支持.txt和.csv格式文件'
            })
        
        phone_unused_path = os.path.join(os.getcwd(), phone_unused_dir)
        os.makedirs(phone_unused_path, exist_ok=True)
        
        # 处理自定义文件名
        custom_name = request.form.get('custom_name')
        if custom_name:
            # 确保自定义文件名有正确的扩展名
            if not custom_name.endswith('.txt'):
                custom_name += '.txt'
            filename = custom_name
        else:
            # 如果是csv文件，转换为txt格式保存
            if file_extension == '.csv':
                filename = os.path.splitext(file.filename)[0] + '.txt'
            else:
                filename = file.filename
        
        file_path = os.path.join(phone_unused_path, filename)
        
        # 如果是csv文件，需要转换格式
        if file_extension == '.csv':
            import csv
            import io
            
            # 读取csv内容
            file_content = file.read().decode('utf-8')
            csv_reader = csv.reader(io.StringIO(file_content))
            
            # 转换为txt格式并保存
            with open(file_path, 'w', encoding='utf-8') as txt_file:
                for row in csv_reader:
                    if row:  # 跳过空行
                        txt_file.write('----'.join(row) + '\n')
        else:
            # 直接保存txt文件
            file.save(file_path)
        
        return jsonify({
            'success': True,
            'message': '文件上传成功'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/api/delete_phone', methods=['POST'])
def delete_phone():
    """删除手机号（备份原文件并将删除的行写入bak文件）"""
    try:
        data = request.get_json()
        phone_number = data.get('phone')
        
        if not phone_number:
            return jsonify({
                'success': False,
                'message': '手机号不能为空'
            })
        
        phone_unused_path = os.path.join(os.getcwd(), phone_unused_dir)
        phone_delete_path = os.path.join(os.getcwd(), phone_delete_dir)
        os.makedirs(phone_delete_path, exist_ok=True)
        
        # 从所有配置文件中查找并删除该手机号
        moved = False
        for file in os.listdir(phone_unused_path):
            if file.endswith('.txt'):
                unused_file = os.path.join(phone_unused_path, file)
                
                # 读取原文件
                lines = []
                if os.path.exists(unused_file):
                    with open(unused_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                
                # 查找并移除手机号
                new_lines = []
                deleted_lines = []
                found = False
                for line in lines:
                    if line.strip() == phone_number:
                        found = True
                        moved = True
                        deleted_lines.append(line)
                    else:
                        new_lines.append(line)
                
                if found:
                    # 创建备份文件名（原文件名_bak）
                    file_name_without_ext = os.path.splitext(file)[0]
                    file_ext = os.path.splitext(file)[1]
                    bak_file_name = f"{file_name_without_ext}_bak{file_ext}"
                    bak_file_path = os.path.join(phone_delete_path, bak_file_name)
                    
                    # 将删除的行写入bak文件
                    with open(bak_file_path, 'a', encoding='utf-8') as f:
                        f.writelines(deleted_lines)
                    
                    # 重写原文件（移除删除的行）
                    with open(unused_file, 'w', encoding='utf-8') as f:
                        f.writelines(new_lines)
        
        if moved:
            return jsonify({
                'success': True,
                'message': '手机号删除成功，原文件已备份'
            })
        else:
            return jsonify({
                'success': False,
                'message': '未找到该手机号'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/api/restore_phone', methods=['POST'])
def restore_phone():
    """恢复手机号（从删除目录移回）"""
    try:
        data = request.get_json()
        phone_number = data.get('phone')
        
        if not phone_number:
            return jsonify({
                'success': False,
                'message': '手机号不能为空'
            })
        
        phone_unused_path = os.path.join(os.getcwd(), phone_unused_dir)
        phone_delete_path = os.path.join(os.getcwd(), phone_delete_dir)
        
        # 从删除目录中查找并恢复该手机号
        restored = False
        for file in os.listdir(phone_delete_path):
            if file.endswith('.txt'):
                delete_file = os.path.join(phone_delete_path, file)
                unused_file = os.path.join(phone_unused_path, file)
                
                # 读取删除文件
                lines = []
                if os.path.exists(delete_file):
                    with open(delete_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                
                # 查找并移除手机号
                new_lines = []
                found = False
                for line in lines:
                    if line.strip() == phone_number:
                        found = True
                        restored = True
                        # 添加到有效文件
                        with open(unused_file, 'a', encoding='utf-8') as f:
                            f.write(line)
                    else:
                        new_lines.append(line)
                
                if found:
                    # 重写删除文件
                    with open(delete_file, 'w', encoding='utf-8') as f:
                        f.writelines(new_lines)
        
        if restored:
            return jsonify({
                'success': True,
                'message': '手机号恢复成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '未找到该手机号'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

# VNC查看器页面路由
@app.route('/vnc_viewer')
def vnc_viewer():
    """VNC查看器页面"""
    return render_template('vnc_viewer.html')

# 处理@vite/client请求，避免404错误（通常由浏览器开发者工具或扩展产生）
@app.route('/@vite/client')
def vite_client():
    """处理vite客户端请求，返回204状态码"""
    return '', 204

# 全局标志，防止重复清理
_cleanup_done = False

# 应用退出时的清理函数
def cleanup_on_exit():
    """应用退出时清理资源"""
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True
    
    logger.info("应用正在退出，开始清理资源...")
    try:
        cleanup_all_vnc_connections()
        logger.info("资源清理完成")
    except Exception as e:
        logger.error(f"清理资源时出错: {str(e)}")

# 注册退出处理函数
import atexit
atexit.register(cleanup_on_exit)

# 信号处理
import signal

def signal_handler(signum, frame):
    """处理系统信号"""
    global _cleanup_done
    if _cleanup_done:
        sys.exit(0)
        
    logger.info(f"收到信号 {signum}，开始清理资源...")
    cleanup_on_exit()
    logger.info("资源清理完成，退出应用")
    sys.exit(0)

# 注册信号处理器
signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # 终止信号

if __name__ == '__main__':
    try:
        logger.info("启动Flask应用...")
        socketio.run(app, debug=False, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        logger.info("收到键盘中断信号")
    except Exception as e:
        logger.error(f"应用运行异常: {str(e)}")
    finally:
        cleanup_on_exit()