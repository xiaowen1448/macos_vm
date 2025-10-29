import os
import json
import logging
import threading
import time
import sys
import shutil
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



def execute_remote_script(ip, username, script_name):
    """通过SSH互信执行目录脚本并获取输出"""
    try:
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
        try:
            ssh.connect(ip, username=username, timeout=10, look_for_keys=True, allow_agent=True)
            ssh_log.append("[SSH] SSH连接建立成功")
        except paramiko.AuthenticationException:
            # 密钥认证失败，尝试密码认证并自动设置互信
            ssh_log.append("[SSH] 密钥认证失败，尝试密码认证")
            try:
                ssh.connect(ip, username=username, password=vm_password, timeout=10)
                ssh_log.append("[SSH] 密码认证成功，开始设置SSH互信")

                # 设置SSH互信
                success, message = setup_ssh_trust(ip, username, vm_password)
                if success:
                    ssh_log.append("[SSH] SSH互信设置成功")
                    # 清理缓存
                    vm_name = get_vm_name_by_ip(ip)
                    if vm_name:
                        vm_cache.clear_cache(vm_name, 'online_status')
                else:
                    ssh_log.append(f"[SSH] SSH互信设置失败: {message}")
            except Exception as pwd_e:
                ssh_log.append(f"[SSH] 密码认证也失败: {str(pwd_e)}")
                ssh.close()
                return False, f"SSH连接失败: {str(pwd_e)}", "\n".join(ssh_log)

        # 检查脚本是否存在
        check_command = f"ls -la {script_name}"
        #  ssh_log.append(f"[SSH] 检查脚本是否存在: {check_command}")
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
            # logger.info(f"脚本 {script_name} 执行成功，输出长度: {len(output)}")
            return True, output, full_log
        else:
            error_msg = error if error else f"脚本 {script_name} 执行失败，退出状态: {exit_status}"
            # logger.error(f"脚本 {script_name} 执行失败: {error_msg}")
            return False, error_msg, full_log

    except ImportError:
        # logger.error("paramiko库未安装")
        return False, "需要安装paramiko库: pip install paramiko", "paramiko库未安装"
    except Exception as e:
        #  logger.error(f"execute_remote_script异常: {str(e)}")
        error_msg = f"通过SSH互信执行脚本时发生错误: {str(e)}"
        return False, error_msg, f"[SSH] 连接异常: {str(e)}"


# 启动时清除所有session，确保每次启动都使用新的session
def clear_sessions_on_startup():
    """启动时清除所有session"""
    try:
        # 清除session文件（如果使用文件session）
        session_dir = os.path.join(os.path.dirname(__file__), 'flask_session')
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
            os.makedirs(session_dir, exist_ok=True)
            logger.info("已清除所有session文件")
    except Exception as e:
        logger.warning(f"清除session文件失败: {e}")

    logger.info("应用启动，所有session已重置")



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

# 在应用启动时执行
clear_sessions_on_startup()
VM_DIRS = {
    '10_12': clone_dir,
    'chengpin': vm_chengpin_dir
}
clone_tasks = {}
tasks = {}
websockify_processes = {}  # 存储websockify进程信息


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

        if success_vms > 0 and failed_vms == 0:
            task['status'] = 'completed'
            add_task_log(task_id, 'success',
                         f'虚拟机克隆成功！所有虚拟机监控和配置完成！成功: {success_vms}, 失败: {failed_vms}')
            logger.info(f"[DEBUG] 虚拟机克隆成功！所有虚拟机监控和配置完成！成功: {success_vms}, 失败: {failed_vms}")
        elif success_vms > 0 and failed_vms > 0:
            task['status'] = 'completed_with_errors'
            add_task_log(task_id, 'warning', f'虚拟机克隆部分成功。成功: {success_vms}, 失败: {failed_vms}')
            logger.info(f"[DEBUG] 虚拟机克隆部分成功。成功: {success_vms}, 失败: {failed_vms}")
        else:
            task['status'] = 'failed'
            add_task_log(task_id, 'error', f'虚拟机克隆失败。成功: {success_vms}, 失败: {failed_vms}')
            logger.info(f"[DEBUG] 虚拟机克隆失败。成功: {success_vms}, 失败: {failed_vms}")

        # 强制刷新，确保前端能立即收到更新
        sys.stdout.flush()


def monitor_vm_and_configure(task_id, vm_name, vm_path, wuma_config_file, max_wait_time=600):
    """监控虚拟机IP和SSH状态，连通后自动配置五码"""
    start_time = time.time()

    # add_task_log(task_id, 'info', f'开始监控虚拟机 {vm_name} 的网络状态...')

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
                # logger.info(f"[DEBUG] 发送监控进度更新: {progress_data}")
                sys.stdout.flush()

    try:
        while time.time() - start_time < max_wait_time:
            try:
                # 获取虚拟机IP（已集成强制重启逻辑）
                vm_ip = get_vm_ip(vm_name)
                if not vm_ip:
                    # add_task_log(task_id, 'debug', f'虚拟机 {vm_name} IP获取失败，等待5秒后重试...')
                    time.sleep(5)
                    continue

                # 检测IP存活
                if not ping_vm_ip(vm_ip):
                    # add_task_log(task_id, 'debug', f'虚拟机 {vm_name} ({vm_ip}) ping不通，等待5秒后重试...')
                    time.sleep(5)
                    continue

                if not check_ssh_connectivity(vm_ip, vm_username):
                    # add_task_log(task_id, 'debug', f'虚拟机 {vm_name} ({vm_ip}) SSH未就绪，等待10秒后重试...')
                    time.sleep(10)
                    continue
                try:
                    result = batch_change_wuma_core([vm_name], wuma_config_file, task_id)

                    if isinstance(result, dict) and result.get('status') == 'success':
                        logger.info(f"[DEBUG] 开始为虚拟机 {vm_name} 执行JU值更改")

                        # 更新五码进度 - 使用线程锁确保线程安全
                        if task_id in clone_tasks and 'monitoring' in clone_tasks[task_id]:
                            # 获取或创建任务锁
                            if not hasattr(clone_tasks[task_id], '_lock'):
                                clone_tasks[task_id]['_lock'] = threading.Lock()

                            with clone_tasks[task_id]['_lock']:
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
                            script_path = f"{sh_script_remote_path}test.sh"
                            success, output, ssh_log = execute_remote_script(vm_ip, vm_username, script_path)
                            if success:
                                add_task_log(task_id, 'success', f'虚拟机 {vm_name} JU值更改成功')
                                add_task_log(task_id, 'info', f'开始重启虚拟机 {vm_name}...')
                                # logger.info(f"[DEBUG] 开始重启虚拟机 {vm_name}")
                                # 更新重启进度 - 使用线程锁确保线程安全
                                if task_id in clone_tasks and 'monitoring' in clone_tasks[task_id]:
                                    # 获取或创建任务锁
                                    if not hasattr(clone_tasks[task_id], '_lock'):
                                        clone_tasks[task_id]['_lock'] = threading.Lock()

                                    with clone_tasks[task_id]['_lock']:
                                        monitoring = clone_tasks[task_id]['monitoring']
                                        # 使用线程安全的方式更新进度
                                        monitoring['restart_progress']['current'] = min(
                                            monitoring['restart_progress']['current'] + 1,
                                            monitoring['restart_progress']['total']
                                        )
                                        current_restart = monitoring['restart_progress']['current']
                                        total_restart = monitoring['restart_progress']['total']
                                        update_monitoring_progress(
                                            restart_progress={'current': current_restart, 'total': total_restart})

                                vmrun_path = get_vmrun_path()

                                # 重启虚拟机
                                reset_cmd = [vmrun_path, 'reset', vm_path]
                                try:
                                    # 增加超时时间到120秒，因为虚拟机重启可能需要较长时间
                                    reset_result = subprocess.run(reset_cmd, capture_output=True, timeout=200)

                                    if reset_result.returncode == 0:
                                        add_task_log(task_id, 'success',
                                                     f'虚拟机 {vm_name} 重启完成，五码和JU值配置全部完成')
                                        logger.info(f"[DEBUG] 虚拟机 {vm_name} 重启完成，五码和JU值配置全部完成")

                                        update_monitoring_progress(success=True)

                                        # 检查是否所有虚拟机都已完成监控
                                        check_and_complete_task(task_id)
                                        return True
                                    else:
                                        add_task_log(task_id, 'error',
                                                     f'虚拟机 {vm_name} 重启失败: {reset_result.stderr.decode("utf-8", errors="ignore")}')
                                        logger.info(
                                            f"[DEBUG] 虚拟机 {vm_name} 重启失败: {reset_result.stderr.decode('utf-8', errors='ignore')}")
                                        update_monitoring_progress(failed=True)

                                        # 检查是否所有虚拟机都已完成监控
                                        check_and_complete_task(task_id)
                                        return False

                                except subprocess.TimeoutExpired:
                                    # 重启超时，但仍然标记为成功，因为reset命令已经发出
                                    add_task_log(task_id, 'warning', f'虚拟机 {vm_name} 重启命令超时，但reset命令已执行')
                                    logger.info(f"[DEBUG] 虚拟机 {vm_name} 重启命令超时，但reset命令已执行")
                                    update_monitoring_progress(success=True)
                                    check_and_complete_task(task_id)
                                    return True

                                except Exception as reset_e:
                                    add_task_log(task_id, 'error', f'虚拟机 {vm_name} 重启异常: {str(reset_e)}')
                                    logger.info(f"[DEBUG] 虚拟机 {vm_name} 重启异常: {str(reset_e)}")
                                    update_monitoring_progress(failed=True)
                                    check_and_complete_task(task_id)
                                    return False
                            else:
                                add_task_log(task_id, 'error', f'虚拟机 {vm_name} JU值更改失败: {output}')
                                logger.info(f"[DEBUG] 虚拟机 {vm_name} JU值更改失败: {output}")
                                update_monitoring_progress(failed=True)

                                # 检查是否所有虚拟机都已完成监控
                                check_and_complete_task(task_id)
                                return False

                        except Exception as ju_e:
                            add_task_log(task_id, 'error', f'虚拟机 {vm_name} JU值更改异常: {str(ju_e)}')
                            logger.info(f"[DEBUG] 虚拟机 {vm_name} JU值更改异常: {str(ju_e)}")
                            update_monitoring_progress(failed=True)
                            check_and_complete_task(task_id)
                            return False
                    else:
                        error_msg = result.get('message', '未知错误') if isinstance(result, dict) else '配置失败'
                        add_task_log(task_id, 'error', f'虚拟机 {vm_name} 五码配置失败: {error_msg}')
                        logger.info(f"[DEBUG] 虚拟机 {vm_name} 五码配置失败: {error_msg}")
                        update_monitoring_progress(failed=True)

                        # 检查是否所有虚拟机都已完成监控
                        check_and_complete_task(task_id)
                        return False
                except Exception as e:
                    error_detail = f'虚拟机 {vm_name} 五码配置异常: {str(e)}'
                    add_task_log(task_id, 'error', error_detail)
                    logger.info(f"[DEBUG] {error_detail}")
                    logger.info(f"[DEBUG] 异常详情: {type(e).__name__}: {str(e)}")

                    logger.info(f"[DEBUG] 异常堆栈: {traceback.format_exc()}")
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
        check_and_complete_task(task_id)
        return False



def batch_change_ju_worker(task_id, selected_vms):
    """批量更改JU值后台工作函数"""
    logger.info(f"开始批量更改JU值任务: {task_id}")

    try:
        # 验证选中的虚拟机是否都在运行
        vmrun_path = get_vmrun_path()

        list_cmd = [vmrun_path, 'list']

        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')

        if result.returncode != 0:
            add_task_log(task_id, 'ERROR', f'获取运行中虚拟机列表失败: {result.stderr}')
            tasks[task_id]['status'] = 'failed'
            return

        running_vms = result.stdout.strip().split('\n')[1:]  # 跳过标题行
        # logger.info(f"获取到运行中虚拟机: {running_vms}")

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
                        #  logger.info(f"找到虚拟机 {vm_name} 的运行路径: {vm_path}")
                        break

                if not vm_path:
                    # logger.error(f"未找到虚拟机 {vm_name} 的运行路径")
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
                script_path = f"{sh_script_remote_path}test.sh"
                logger.info(f"执行test.sh脚本: {script_path}")
                add_task_log(task_id, 'INFO', f'执行test.sh脚本: {vm_name}')
                success, output, ssh_log = execute_remote_script(vm_ip, 'wx', script_path)

                if not success:
                    add_task_log(task_id, 'ERROR', f'test.sh脚本执行失败: {output}')
                    tasks[task_id]['results'].append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': f'test.sh脚本执行失败: {test_result.stderr}'
                    })
                    continue

                add_task_log(task_id, 'INFO', f'test.sh脚本执行成功: {vm_name}')

                # 重启虚拟机
                add_task_log(task_id, 'INFO', f'开始重启虚拟机: {vm_name}')
                restart_cmd = [vmrun_path, 'reset', vm_path]
                logger.info(f"重启虚拟机: {restart_cmd}")
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


# 克隆任务日志流
def clone_vm_worker(task_id):
    """克隆虚拟机工作线程"""
    task = clone_tasks[task_id]
    params = task['params']

    # 调试打印：任务参数
    logger.info(f"[DEBUG] 任务ID: {task_id}")
    logger.info(f"[DEBUG] 任务参数: {params}")

    try:
        # 添加开始日志
        add_task_log(task_id, 'info', f'开始克隆任务: 模板={params["templateVM"]}, 数量={params["cloneCount"]}')
        logger.info(f"[DEBUG] 开始克隆任务: 模板={params['templateVM']}, 数量={params['cloneCount']}")

        # 验证模板虚拟机是否存在
        template_vm_name = params['templateVM']
        template_path = None

        # 在虚拟机模板目录中查找匹配的.vmx文件
        vm_template_dir = template_dir  # 使用从config导入的虚拟机模板目录
        if os.path.exists(vm_template_dir):
            for root, dirs, files in os.walk(vm_template_dir):
                for file in files:
                    # 灵活匹配：可以是完整的.vmx文件名，或者文件名前缀加.vmx
                    if (file == template_vm_name and file.endswith('.vmx')) or \
                       (file == template_vm_name + '.vmx'):
                        template_path = os.path.join(root, file)
                        break
                if template_path:
                    break
        if not template_path or not os.path.exists(template_path):
            add_task_log(task_id, 'error', f'模板虚拟机不存在: {template_vm_name}（请确保模板目录中存在.vmx文件）')
            task['status'] = 'failed'
            return

        # 确保目标目录存在
        target_dir = clone_dir  # 使用全局配置中的克隆目录
        os.makedirs(target_dir, exist_ok=True)
        # add_task_log(task_id, 'info', f'目标目录: {target_dir}')
        # logger.info(f"[DEBUG] 目标目录创建/确认完成")
        # 创建虚拟机快照（如果启用）
        create_snapshot = params.get('createSnapshot', 'true') == 'true'
        snapshot_name = None
        logger.info(f"[DEBUG] 是否创建快照: {create_snapshot}")
        if create_snapshot:
            add_task_log(task_id, 'info', '开始创建虚拟机快照...')
            logger.info(f"[DEBUG] 开始创建虚拟机快照...")
            vmrun_path = get_vmrun_path()
            # logger.info(f"[DEBUG] vmrun路径: {vmrun_path}")
            logger.info(f"[DEBUG] vmrun是否存在: {os.path.exists(vmrun_path)}")

            # 生成快照名称
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            vm_name_without_ext = params['templateVM'].replace('.vmx', '')
            # 使用用户自定义的快照命名模式
            snapshot_pattern = params.get('snapshotName', '{vmname}_snapshot_{timestamp}')
            if snapshot_pattern == 'custom':
                snapshot_pattern = params.get('customSnapshotName', '{vmname}_snapshot_{timestamp}')
            snapshot_name = snapshot_pattern.replace('{vmname}', vm_name_without_ext).replace('{timestamp}', timestamp)
            snapshot_cmd = [
                vmrun_path,
                '-T', 'ws',
                'snapshot',
                template_path,
                snapshot_name
            ]
            try:
                #  add_task_log(task_id, 'info', f'执行快照命令: vmrun snapshot {template_path} {snapshot_name}')
                start_time = datetime.now()
                result = subprocess.run(snapshot_cmd, capture_output=True, text=True, timeout=120, encoding='utf-8',
                                        errors='ignore')
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                if result.stderr:
                    logger.info(f"[DEBUG] 快照命令错误: {result.stderr}")
                if result.returncode == 0:
                    add_task_log(task_id, 'success', f'虚拟机快照创建成功: {snapshot_name}')
                #   logger.info(f"[DEBUG] 快照创建成功: {snapshot_name}")
                else:
                    add_task_log(task_id, 'error', f'虚拟机快照创建失败: {result.stderr}')
                    logger.info(f"[DEBUG] 快照创建失败: {result.stderr}")
                    task['status'] = 'failed'
                    return
            except subprocess.TimeoutExpired:
                add_task_log(task_id, 'error', '虚拟机快照创建超时')
                logger.info(f"[DEBUG] 快照创建超时")
                task['status'] = 'failed'
                return
            except Exception as e:
                add_task_log(task_id, 'error', f'虚拟机快照创建时发生错误: {str(e)}')
                logger.info(f"[DEBUG] 快照创建异常: {str(e)}")
                task['status'] = 'failed'
                return
        else:
            add_task_log(task_id, 'info', '跳过快照创建，直接开始克隆任务')
        # logger.info(f"[DEBUG] 跳过快照创建，直接开始克隆任务")
        config_file = params.get('configPlist')
        wuma_codes = []
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

            # logger.info(f"[DEBUG] 读取到有效五码数量: {len(wuma_codes)}")
            except Exception as e:
                logger.info(f"[DEBUG] 读取五码配置文件失败: {str(e)}")
                add_task_log(task_id, 'error', f'读取五码配置文件失败: {str(e)}')
                task['status'] = 'failed'
                return
        else:
            logger.info(f"[DEBUG] 五码配置文件不存在: {config_file}")
            add_task_log(task_id, 'error', f'五码配置文件不存在: {config_file}')
            task['status'] = 'failed'
            return

        logger.info(f"[DEBUG] 找到有效五码数量: {len(wuma_codes)}")
        logger.info(f"[DEBUG] 五码列表: {wuma_codes[:3]}...")  # 只显示前3个

        # 开始克隆
        clone_count = int(params['cloneCount'])
        # logger.info(f"[DEBUG] 开始克隆，总数: {clone_count}")

        # 验证克隆数量与五码数量是否匹配
        if clone_count > len(wuma_codes):
            error_msg = f'克隆数量({clone_count})超过可用五码数量({len(wuma_codes)})，请确保五码数量足够'
            add_task_log(task_id, 'error', error_msg)
            logger.info(f"[DEBUG] 错误: {error_msg}")
            task['status'] = 'failed'
            return
        elif clone_count < len(wuma_codes):
            warning_msg = f'五码数量({len(wuma_codes)})多于克隆数量({clone_count})，将使用前{clone_count}个五码'
            # add_task_log(task_id, 'warning', warning_msg)
            # logger.info(f"[DEBUG] 警告: {warning_msg}")
            # 截取需要的五码数量
            wuma_codes = wuma_codes[:clone_count]

        # 生成统一的时间戳，用于所有虚拟机
        unified_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # logger.info(f"[DEBUG] 使用统一时间戳: {unified_timestamp}")

        #  add_task_log(task_id, 'info', f'找到 {len(wuma_codes)} 个有效五码，需要克隆 {clone_count} 个虚拟机，数量匹配验证通过')

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
                #  logger.info(f"[DEBUG] 开始克隆第 {i+1}/{clone_count} 个虚拟机")

                # 生成虚拟机名称和文件夹名称（使用统一时间戳）
                timestamp = unified_timestamp
                vm_name_pattern = params['namingPattern']
                if vm_name_pattern == 'custom':
                    vm_name_pattern = params.get('customNamingPattern', 'VM_{timestamp}_{index}')

                #  logger.info(f"[DEBUG] 虚拟机命名模式: {vm_name_pattern}")

                # 如果命名模式中没有包含 {vmname} 占位符，则将默认前缀 VM 替换为所选模板的基名（去除 .vmx），使命名更具可读性
                # 例如: 原默认 'VM_{timestamp}_{index}' -> 'TemplateName_{timestamp}_{index}'
                if '{vmname}' not in vm_name_pattern:
                    try:
                        template_vm = params.get('templateVM', '')
                        template_base = os.path.splitext(template_vm)[0] if template_vm else 'VM'
                        # 仅替换最左侧的 VM 标识，避免误替换其它部分
                        if vm_name_pattern.startswith('VM'):
                            vm_name_pattern = vm_name_pattern.replace('VM', template_base, 1)
                    except Exception:
                        pass

                # 生成虚拟机名称（不包含.vmx扩展名）
                vm_name_without_ext_generated = vm_name_pattern.replace('{timestamp}', timestamp).replace('{index}', str(i + 1)).replace('{vmname}', vm_name_without_ext)

                # 创建虚拟机文件夹名称
                vm_folder_name = vm_name_without_ext_generated
                vm_folder_path = os.path.join(target_dir, vm_folder_name)

                # 确保虚拟机文件夹存在
                os.makedirs(vm_folder_path, exist_ok=True)
                logger.info(f"[DEBUG] 创建虚拟机文件夹: {vm_folder_path}")

                # 生成完整的虚拟机文件路径
                vm_name = vm_name_without_ext_generated + '.vmx'
                vm_file_path = os.path.join(vm_folder_path, vm_name)
                # 分配五码
                wuma_code = wuma_codes[i % len(wuma_codes)] if wuma_codes else None
                add_task_log(task_id, 'info', f'开始克隆第 {i + 1}/{clone_count} 个虚拟机: {vm_name}')
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

                #   logger.info(f"[DEBUG] 克隆使用的vmrun路径: {vmrun_path}")

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
                # add_task_log(task_id, 'info', f'从快照克隆: {snapshot_name}')
                # logger.info(f"[DEBUG] 从快照克隆: {snapshot_name}")
                else:
                    # 直接从模板克隆
                    clone_cmd = [
                        vmrun_path,
                        'clone',
                        template_path,
                        vm_file_path,
                        'linked'
                    ]
                start_time = datetime.now()
                logger.info(f"[DEBUG] 命令开始时间: {start_time}")

                result = subprocess.run(clone_cmd, capture_output=True, text=True, timeout=300, encoding='utf-8',
                                        errors='ignore')

                # 记录命令结束时间
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                if result.stderr:
                    logger.info(f"[DEBUG] 克隆命令错误: {result.stderr}")
                if result.stdout:
                    add_task_log(task_id, 'info', f'命令输出: {result.stdout.strip()}')
                if result.stderr:
                    add_task_log(task_id, 'warning', f'命令错误: {result.stderr.strip()}')

                if result.returncode == 0:
                    #  add_task_log(task_id, 'success', f'虚拟机 {vm_name} 克隆成功')
                    #  logger.info(f"[DEBUG] 虚拟机 {vm_name} 克隆成功")
                    task['stats']['success'] += 1

                    # 更新vmx文件中的displayName
                    vm_display_name = vm_name_without_ext_generated  # 使用虚拟机文件夹名称作为显示名称
                    if update_vmx_display_name(vm_file_path, vm_display_name):
                        #  add_task_log(task_id, 'info', f'虚拟机 {vm_name} 的displayName已更新为: {vm_display_name}')
                        logger.info(f"[DEBUG] displayName更新成功: {vm_display_name}")
                    else:
                        # add_task_log(task_id, 'warning', f'虚拟机 {vm_name} 的displayName更新失败')
                        logger.info(f"[DEBUG] displayName更新失败")

                    # 添加UUID配置参数
                    if add_uuid_config_to_vmx(vm_file_path):
                        logger.info(f"[DEBUG] UUID配置添加成功")
                    else:
                        logger.info(f"[DEBUG] UUID配置添加失败")

                    # 重写虚拟机uuid参数
                    # new_lines = []
                    # logger.info(f"[DEBUG]开始重写uuid：{vm_file_path}")
                    # with open(vm_file_path, "r", encoding="utf-8") as f:
                    #     for line in f:
                    #         if line.strip().startswith(("uuid.bios", "uuid.location")):
                    #             continue
                    #         new_lines.append(line)

                    # 清理nvram
                    # 删除 nvram
                    # logger.info(f"[DEBUG]开始删除 nvram：{vm_folder_path}")
                    # for f in os.listdir(vm_folder_path):
                    #     if f.endswith(".nvram"):
                    #          os.remove(os.path.join(vm_folder_path, f))

                    # 添加VNC配置
                    vnc_port = get_next_vnc_port()
                    if add_vnc_config_to_vmx(vm_file_path, vnc_port):
                        # add_task_log(task_id, 'info', f'虚拟机 {vm_name} 的VNC配置已添加，端口: {vnc_port}')
                        logger.info(f"[DEBUG] VNC配置添加成功，端口: {vnc_port}")
                    else:
                        add_task_log(task_id, 'warning', f'虚拟机 {vm_name} 的VNC配置添加失败')
                        logger.info(f"[DEBUG] VNC配置添加失败")

                    # 如果配置了自动启动或者配置了五码文件（需要启动虚拟机进行后续配置）
                    should_start = params.get('autoStart') == 'true' or params.get('configPlist')
                    if should_start:
                        # start_reason = "用户勾选自动启动" if params.get('autoStart') == 'true' else "需要进行五码配置"
                        start_cmd = [vmrun_path, 'start', vm_file_path, 'nogui']
                        # add_task_log(task_id, 'info', f'启动虚拟机 ({vm_name})')

                        # 记录启动命令开始时间
                        start_time = datetime.now()
                        # logger.info(f"[DEBUG] 启动命令开始时间: {start_time}")

                        result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=60, encoding='utf-8',
                                                errors='ignore')

                        # 记录启动命令结束时间
                        end_time = datetime.now()
                        duration = (end_time - start_time).total_seconds()
                        if result.stderr:
                            logger.info(f"[DEBUG] 启动命令错误: {result.stderr}")

                        # 记录详细的启动执行结果
                        #  add_task_log(task_id, 'info', f'启动命令执行完成，返回码: {result.returncode}, 耗时: {duration:.2f}秒')
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
                    logger.info(f"[DEBUG] 虚拟机 {vm_name} 克隆失败: {result.stderr}")
                    task['stats']['error'] += 1

                # 更新进度
                task['progress']['current'] = i + 1
                logger.info(f"[DEBUG] 更新进度: {i + 1}/{clone_count}")
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
                add_task_log(task_id, 'error', f'克隆第 {i + 1} 个虚拟机超时')
                logger.info(f"[DEBUG] 克隆第 {i + 1} 个虚拟机超时")
                task['stats']['error'] += 1
            except Exception as e:
                add_task_log(task_id, 'error', f'克隆第 {i + 1} 个虚拟机时发生错误: {str(e)}')
                logger.info(f"[DEBUG] 克隆第 {i + 1} 个虚拟机时发生错误: {str(e)}")
                task['stats']['error'] += 1

        # 任务完成
        logger.info(f"[DEBUG] 任务完成统计 - 成功: {task['stats']['success']}, 失败: {task['stats']['error']}")

        # 如果有成功克隆的虚拟机且配置了五码文件，启动动态监控和配置流程
        if task['stats']['success'] > 0 and params.get('configPlist'):
            add_task_log(task_id, 'info', '开始启动虚拟机监控和自动配置流程...')
            logger.info(f"[DEBUG] 开始启动虚拟机监控和自动配置流程...")

            try:
                # 收集成功克隆的虚拟机信息（使用相同的统一时间戳）
                cloned_vms_info = []
                for i in range(clone_count):
                    timestamp = unified_timestamp  # 使用克隆时的统一时间戳
                    vm_name_pattern = params['namingPattern']
                    if vm_name_pattern == 'custom':
                        vm_name_pattern = params.get('customNamingPattern', 'VM_{timestamp}_{index}')

                    if '{vmname}' not in vm_name_pattern:
                        try:
                            template_vm = params.get('templateVM', '')
                            template_base = os.path.splitext(template_vm)[0] if template_vm else 'VM'
                            if vm_name_pattern.startswith('VM'):
                                vm_name_pattern = vm_name_pattern.replace('VM', template_base, 1)
                        except Exception:
                            pass

                    vm_name_without_ext_generated = vm_name_pattern.replace('{timestamp}', timestamp).replace('{index}', str(i + 1)).replace('{vmname}', vm_name_without_ext)
                    vm_folder_name = vm_name_without_ext_generated
                    vm_folder_path = os.path.join(target_dir, vm_folder_name)
                    vm_name = vm_name_without_ext_generated + '.vmx'
                    vm_file_path = os.path.join(vm_folder_path, vm_name)

                    logger.info(f"[DEBUG] 检查虚拟机文件: {vm_file_path}")
                    if os.path.exists(vm_file_path):
                        cloned_vms_info.append({
                            'name': vm_name_without_ext_generated,
                            'path': vm_file_path
                        })
                        logger.info(f"[DEBUG] 找到成功克隆的虚拟机: {vm_name_without_ext_generated}")
                    else:
                        logger.info(f"[DEBUG] 虚拟机文件不存在: {vm_file_path}")

                if cloned_vms_info:
                    add_task_log(task_id, 'info', f'找到 {len(cloned_vms_info)} 个成功克隆的虚拟机，启动监控线程')
                    logger.info(f"[DEBUG] 找到 {len(cloned_vms_info)} 个成功克隆的虚拟机")

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

                        # add_task_log(task_id, 'info', f'已启动虚拟机 {vm_name} 的监控线程')
                        # logger.info(f"[DEBUG] 已启动虚拟机 {vm_name} 的监控线程")

                        # 避免同时启动太多线程
                        time.sleep(2)

                    add_task_log(task_id, 'info', '所有虚拟机监控线程已启动，将在后台继续执行')
                    # logger.info(f"[DEBUG] 所有虚拟机监控线程已启动")

                    # 不要立即标记任务完成，让监控线程继续运行
                    # 任务状态保持为'running'，直到所有监控完成
                    add_task_log(task_id, 'info', '克隆阶段完成，正在进行虚拟机配置...')

                else:
                    add_task_log(task_id, 'warning', '未找到成功克隆的虚拟机，跳过监控配置')
                    logger.info(f"[DEBUG] 未找到成功克隆的虚拟机，跳过监控配置")

                    # 没有监控任务时才标记完成
                    if task['stats']['error'] == 0:
                        task['status'] = 'completed'
                        add_task_log(task_id, 'success', f'虚拟机克隆完成！成功: {task["stats"]["success"]}')
                        logger.info(f"[DEBUG] 虚拟机克隆完成！成功: {task['stats']['success']}")
                    else:
                        task['status'] = 'completed_with_errors'
                        add_task_log(task_id, 'warning',
                                     f'克隆任务完成，但有错误。成功: {task["stats"]["success"]}, 失败: {task["stats"]["error"]}')
                        logger.info(
                            f"[DEBUG] 克隆任务完成，但有错误。成功: {task['stats']['success']}, 失败: {task['stats']['error']}")

            except Exception as e:
                add_task_log(task_id, 'error', f'启动虚拟机监控时发生错误: {str(e)}')
                logger.info(f"[DEBUG] 启动虚拟机监控时发生错误: {str(e)}")

                # 发生错误时才标记完成
                if task['stats']['error'] == 0:
                    task['status'] = 'completed'
                    add_task_log(task_id, 'success', f'虚拟机克隆完成！成功: {task["stats"]["success"]}')
                    logger.info(f"[DEBUG] 虚拟机克隆完成！成功: {task['stats']['success']}")
                else:
                    task['status'] = 'completed_with_errors'
                    add_task_log(task_id, 'warning',
                                 f'克隆任务完成，但有错误。成功: {task["stats"]["success"]}, 失败: {task["stats"]["error"]}')
                    logger.info(
                        f"[DEBUG] 克隆任务完成，但有错误。成功: {task['stats']['success']}, 失败: {task['stats']['error']}")

    except Exception as e:
        add_task_log(task_id, 'error', f'克隆任务发生严重错误: {str(e)}')
        logger.info(f"[DEBUG] 克隆任务发生严重错误: {str(e)}")
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

        logger.info(f"[DEBUG] 分配VNC端口: {next_port}，已更新config.ini")
        return next_port

    except Exception as e:
        logger.info(f"[DEBUG] 获取VNC端口失败: {str(e)}")
        # 如果出错，返回默认端口
        return vnc_start_port


def read_vmx_file_smart(vmx_file_path):
    """智能读取VMX文件，尝试多种编码"""
    encodings = ['utf-8', 'ansi', 'latin-1', 'cp1252']
    for encoding in encodings:
        try:
            with open(vmx_file_path, 'r', encoding=encoding) as f:
                content = f.read()
                return content, encoding
        except (UnicodeDecodeError, LookupError):
            continue
    return None, None

def add_uuid_config_to_vmx(vmx_file_path):
    """在VMX文件中添加UUID配置参数"""
    try:
        logger.info(f"[DEBUG] 开始添加UUID配置到vmx文件: {vmx_file_path}")

        # 检查文件是否存在
        if not os.path.exists(vmx_file_path):
            logger.info(f"[DEBUG] vmx文件不存在: {vmx_file_path}")
            return False

        # 使用智能编码读取vmx文件
        content, detected_encoding = read_vmx_file_smart(vmx_file_path)
        if content is None:
            logger.error(f"[DEBUG] 无法使用任何编码读取vmx文件: {vmx_file_path}")
            return False

        lines = content.splitlines(keepends=True)
        logger.info(f"[DEBUG] 成功使用 {detected_encoding} 编码读取vmx文件")

        logger.info(f"[DEBUG] 读取到 {len(lines)} 行内容")

        # 检查是否已存在uuid.action配置，如果存在则更新，否则添加
        uuid_config_key = 'uuid.action'
        uuid_config_value = 'create'

        config_found = False

        # 查找并更新已存在的uuid.action配置
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped.startswith(uuid_config_key):
                old_line = line_stripped
                new_line = f'{uuid_config_key} = "{uuid_config_value}"\n'
                lines[i] = new_line
                config_found = True
                logger.info(f"[DEBUG] 更新UUID配置: {old_line} -> {new_line.strip()}")
                break

        # 如果未找到uuid.action配置，则添加
        if not config_found:
            new_line = f'{uuid_config_key} = "{uuid_config_value}"\n'
            lines.append(new_line)
            logger.info(f"[DEBUG] 添加UUID配置: {new_line.strip()}")

        # 写回文件，使用ANSI编码防止VMware乱码
        try:
            with open(vmx_file_path, 'w', encoding='ansi') as f:
                f.writelines(lines)
            logger.info(f"[DEBUG] UUID配置添加成功，使用ANSI编码写入")
        except UnicodeEncodeError:
            # 如果ANSI编码失败，回退到UTF-8
            logger.info(f"[DEBUG] ANSI编码写入失败，回退到UTF-8编码")
            with open(vmx_file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            logger.info(f"[DEBUG] UUID配置添加成功，使用UTF-8编码写入")

        return True

    except Exception as e:
        logger.info(f"[DEBUG] 添加UUID配置失败: {str(e)}")
        return False


def add_vnc_config_to_vmx(vmx_file_path, vnc_port):
    """在VMX文件中添加VNC配置参数"""
    try:
        # logger.info(f"[DEBUG] 开始添加VNC配置到vmx文件: {vmx_file_path}")
        logger.info(f"[DEBUG] VNC端口: {vnc_port}")

        # 检查文件是否存在
        if not os.path.exists(vmx_file_path):
            logger.info(f"[DEBUG] vmx文件不存在: {vmx_file_path}")
            return False

        # 使用智能编码读取vmx文件
        content, detected_encoding = read_vmx_file_smart(vmx_file_path)
        if content is None:
            logger.error(f"[DEBUG] VNC配置：无法使用任何编码读取vmx文件: {vmx_file_path}")
            return False

        lines = content.splitlines(keepends=True)
        logger.info(f"[DEBUG] VNC配置：成功使用 {detected_encoding} 编码读取vmx文件")

        logger.info(f"[DEBUG] 读取到 {len(lines)} 行内容")

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
                    logger.info(f"[DEBUG] 更新VNC配置: {old_line} -> {new_line.strip()}")
                    break

        # 添加未找到的VNC配置
        for config_key, config_value in vnc_configs.items():
            if config_key not in updated_configs:
                new_line = f'{config_key} = "{config_value}"\n'
                lines.append(new_line)
            # logger.info(f"[DEBUG] 添加VNC配置: {new_line.strip()}")

        # 写回文件，使用ANSI编码防止VMware乱码
        try:
            with open(vmx_file_path, 'w', encoding='ansi') as f:
                f.writelines(lines)
            logger.info(f"[DEBUG] VNC配置添加成功，使用ANSI编码写入")
        except UnicodeEncodeError:
            # 如果ANSI编码失败，回退到UTF-8
            logger.info(f"[DEBUG] VNC配置：ANSI编码写入失败，回退到UTF-8编码")
            with open(vmx_file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            logger.info(f"[DEBUG] VNC配置添加成功，使用UTF-8编码写入")

        return True

    except Exception as e:
        #  logger.info(f"[DEBUG] 添加VNC配置失败: {str(e)}")
        return False


def update_vmx_display_name(vmx_file_path, new_display_name):
    """更新vmx文件中的displayName参数并修改编码为ANSI"""
    try:
        logger.info(f"[DEBUG] 开始更新vmx文件: {vmx_file_path}")
        logger.info(f"[DEBUG] 新的displayName: {new_display_name}")

        # 检查文件是否存在
        if not os.path.exists(vmx_file_path):
            logger.info(f"[DEBUG] vmx文件不存在: {vmx_file_path}")
            return False, f"vmx文件不存在: {vmx_file_path}"

        # 使用智能编码读取vmx文件
        content, detected_encoding = read_vmx_file_smart(vmx_file_path)
        if content is None:
            logger.error(f"[DEBUG] DisplayName更新：无法使用任何编码读取vmx文件: {vmx_file_path}")
            return False, f"无法使用任何编码读取vmx文件: {vmx_file_path}"

        lines = content.splitlines(keepends=True)
        logger.info(f"[DEBUG] DisplayName更新：成功使用 {detected_encoding} 编码读取vmx文件")

        logger.info(f"[DEBUG] 读取到 {len(lines)} 行内容")

        # 查找并替换displayName参数和编码参数
        displayname_updated = False
        encoding_updated = False

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped.startswith('displayName'):
                old_line = line_stripped
                new_line = f'displayName = "{new_display_name}"\n'
                lines[i] = new_line
                displayname_updated = True
                logger.info(f"[DEBUG] 找到displayName行: {old_line}")
                logger.info(f"[DEBUG] 更新为: {new_line.strip()}")
            elif line_stripped.startswith('.encoding'):
                old_encoding_line = line_stripped
                new_encoding_line = '.encoding = "GBK"\n'
                lines[i] = new_encoding_line
                encoding_updated = True
                logger.info(f"[DEBUG] 找到编码行: {old_encoding_line}")
                logger.info(f"[DEBUG] 更新为: {new_encoding_line.strip()}")

        if not displayname_updated:
            # 如果没有找到displayName行，在文件开头添加
            new_line = f'displayName = "{new_display_name}"\n'
            lines.insert(1, new_line)  # 在编码行后添加
            logger.info(f"[DEBUG] 未找到displayName行，在文件开头添加: {new_line.strip()}")

        if not encoding_updated:
            # 如果没有找到编码行，在文件开头添加
            new_encoding_line = '.encoding = "GBK"\n'
            lines.insert(0, new_encoding_line)
            logger.info(f"[DEBUG] 未找到编码行，在文件开头添加: {new_encoding_line.strip()}")

        # 写回文件，使用GBK编码防止VMware乱码
        write_encoding = 'gbk'
        try:
            with open(vmx_file_path, 'w', encoding='gbk') as f:
                f.writelines(lines)
            logger.info(f"[DEBUG] DisplayName更新：vmx文件更新成功，使用GBK编码写入")
        except UnicodeEncodeError:
            # 如果GBK编码失败，回退到UTF-8
            write_encoding = 'utf-8'
            logger.info(f"[DEBUG] DisplayName更新：GBK编码写入失败，回退到UTF-8编码")
            with open(vmx_file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            logger.info(f"[DEBUG] DisplayName更新：vmx文件更新成功，使用UTF-8编码写入")

        # 验证更新结果，使用相同的编码读取
        try:
            with open(vmx_file_path, 'r', encoding=write_encoding) as f:
                content = f.read()
                if f'displayName = "{new_display_name}"' in content:
                    logger.info(f"[DEBUG] 验证成功：displayName已正确更新")
                    return True, "displayName和编码更新成功"
                else:
                    logger.info(f"[DEBUG] 验证失败：displayName未找到")
                    return False, "验证失败：displayName未找到"
        except UnicodeDecodeError:
            # 验证时如果编码失败，尝试其他编码
            for encoding in encodings_to_try:
                try:
                    with open(vmx_file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                        if f'displayName = "{new_display_name}"' in content:
                            logger.info(f"[DEBUG] 验证成功：displayName已正确更新（使用{encoding}编码验证）")
                            return True, "displayName和编码更新成功"
                except UnicodeDecodeError:
                    continue
            logger.info(f"[DEBUG] 验证失败：无法读取文件进行验证")
            return False, "验证失败：无法读取文件进行验证"

    except Exception as e:
        logger.info(f"[DEBUG] 更新vmx文件失败: {str(e)}")
        return False, f"更新vmx文件失败: {str(e)}"


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
            logger.info(f"[DEBUG] 写入日志文件失败: {str(e)}")



# 克隆后等待执行更改五码的操作
def batch_change_wuma_core(selected_vms, config_file_path, task_id=None):
    """批量更改五码核心函数"""
    logger.info(f"开始批量更改五码核心处理，虚拟机数量: {len(selected_vms)}")
    logger.info(f"使用配置文件: {config_file_path}")

    def log_message(level, message):
        """统一日志记录函数"""
        logger.info(message)
        if task_id:
            add_task_log(task_id, level, message)

    # 五码分配锁文件路径
    lock_file_path = config_file_path + '.lock'

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

        # 使用文件锁确保五码分配的原子性
        logger.debug(f"尝试获取五码配置文件锁: {lock_file_path}")
        with open(lock_file_path, 'w') as lock_file:
            # 获取文件锁，最多等待30秒
            max_wait_time = 30
            start_time = time.time()
            while True:
                try:
                    if os.name == 'nt' and msvcrt:  # Windows系统
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    elif fcntl:  # Unix/Linux系统
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    else:
                        # 如果没有可用的文件锁机制，使用简单的文件存在检查
                        if os.path.exists(lock_file_path + '.busy'):
                            raise IOError("Lock file exists")
                        with open(lock_file_path + '.busy', 'w') as busy_file:
                            busy_file.write(str(os.getpid()))
                    logger.debug("成功获取五码配置文件锁")
                    break
                except (IOError, OSError):
                    if time.time() - start_time > max_wait_time:
                        logger.error("获取五码配置文件锁超时")
                        return {
                            'status': 'error',
                            'message': '五码配置文件被其他进程占用，请稍后重试'
                        }
                    time.sleep(0.1)

            # 在锁保护下读取和分配五码
            with open(config_file_path, 'r', encoding='utf-8') as f:
                wuma_lines = f.readlines()

            # 过滤有效行
            valid_wuma_lines = [line.strip() for line in wuma_lines if
                                line.strip() and is_valid_wuma_file_line(line.strip())]

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

            # 为当前批次分配五码（取前N个）
            allocated_wuma_lines = valid_wuma_lines[:len(selected_vms)]
            remaining_wuma_lines = valid_wuma_lines[len(selected_vms):]

            # 立即更新配置文件，移除已分配的五码
            with open(config_file_path, 'w', encoding='utf-8') as f:
                for line in remaining_wuma_lines:
                    f.write(line + '\n')

            logger.info(f"已分配 {len(allocated_wuma_lines)} 个五码，剩余 {len(remaining_wuma_lines)} 个")

            # 释放文件锁后继续处理
            try:
                if os.name == 'nt' and msvcrt:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                elif fcntl:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                else:
                    # 删除简单锁文件
                    busy_lock_path = lock_file_path + '.busy'
                    if os.path.exists(busy_lock_path):
                        os.remove(busy_lock_path)
            except Exception as lock_error:
                logger.warning(f"释放文件锁时出错: {lock_error}")

        # 验证选中的虚拟机是否都在运行
        vmrun_path = get_vmrun_path()

        list_cmd = [vmrun_path, 'list']
        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')

        if result.returncode != 0:
            return {
                'status': 'error',
                'message': f'获取运行中虚拟机列表失败: {result.stderr}'
            }

        running_vms = result.stdout.strip().split('\n')[1:]  # 跳过标题行
        # logger.info(f"获取到运行中虚拟机: {running_vms}")
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

        # 检测母盘版本并选择合适的plist模板
        def detect_macos_version(vm_name):
            """检测虚拟机的macOS版本"""
            # 检查虚拟机名称中是否包含版本信息
            vm_name_lower = vm_name.lower()
            if any(version in vm_name_lower for version in
                   ['macos10.15', 'macos11','macos12','macos13','macos14', 'macos15']):
                return 'macos10.15+'
            elif any(version in vm_name_lower for version in
                     ['macos10.12', 'macos10.13', 'macos10.14']):
                return 'legacy'
            else:
                # 默认使用legacy模板（向后兼容）
                return 'legacy'

        # 检测第一个虚拟机的版本来决定使用哪个模板
        first_vm = selected_vms[0] if selected_vms else ''
        macos_version = detect_macos_version(first_vm)

        # 根据版本选择模板文件
        if macos_version == 'macos10.15+':
            template_filename = 'opencore.plist'
            logger.info(f"检测到macos10.15+版本，使用OpenCore模板")
        else:
            template_filename = 'temp.plist'
            logger.info(f"检测到legacy版本，使用Clover模板")

        plist_template_path = os.path.join(plist_template_dir, template_filename)
        logger.info(f"检查plist模板文件: {plist_template_path}")
        if not os.path.exists(plist_template_path):
            logger.error(f"plist模板文件不存在: {plist_template_path}")
            return {
                'status': 'error',
                'message': f'plist模板文件不存在: {plist_template_path}'
            }

        logger.info(f"plist模板文件存在，开始读取...")
        with open(plist_template_path, 'r', encoding='utf-8') as f:
            plist_template = f.read()
        logger.info(f"plist模板读取完成，长度: {len(plist_template)}")

        # 创建备份目录
        backup_dir = wuma_config_install_dir
        logger.info(f"创建备份目录: {backup_dir}")
        os.makedirs(backup_dir, exist_ok=True)

        results = []
        used_wuma_lines = []

        # 为每个选中的虚拟机生成plist文件
        for i, vm_name in enumerate(selected_vms):
            if i >= len(allocated_wuma_lines):
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
                    # logger.info(f"找到虚拟机 {vm_name} 的运行路径: {vm_path}")
                    break

            if not vm_path:
                # log_message('error', f'未找到虚拟机 {vm_name} 的运行路径')
                results.append({
                    'vm_name': vm_name,
                    'success': False,
                    'message': '未找到虚拟机运行路径'
                })
                continue

            try:
                # 解析五码数据
                wuma_line = allocated_wuma_lines[i]
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
                        rom_pairs = [rom[i:i + 2] for i in range(0, len(rom), 2)]
                        rom_bytes = bytes([int(pair, 16) for pair in rom_pairs])

                    rom_base64 = base64.b64encode(rom_bytes).decode('utf-8')
                    rom_formatted = rom_base64  # 格式化为 ROM :base64结果
                    logger.info(
                        f"ROM原始值: {rom}, PowerShell风格字节: {rom_bytes}, base64加密后: {rom_base64}, 格式化后: {rom_formatted}")
                except ValueError as e:
                    logger.error(f"ROM PowerShell风格转换失败: {e}, 使用UTF-8编码")
                    rom_bytes = rom.encode('utf-8')
                    rom_base64 = base64.b64encode(rom_bytes).decode('utf-8')
                    rom_formatted = rom_base64
                    logger.info(
                        f"ROM原始值: {rom}, UTF-8编码后: {rom_bytes}, base64加密后: {rom_base64}, 格式化后: {rom_formatted}")

                # 替换plist模板中的占位符
                plist_content = plist_template
                plist_content = plist_content.replace('$1', model)
                plist_content = plist_content.replace('$3', serial_number)
                plist_content = plist_content.replace('$5', rom_formatted)  # 使用格式化后的ROM
                plist_content = plist_content.replace('$6', mlb)
                plist_content = plist_content.replace('$7', sm_uuid)

                # 对于legacy版本（Clover），需要替换$2和$4占位符
                if macos_version == 'legacy':
                    plist_content = plist_content.replace('$2', board_id)  # Board-ID for Clover
                    plist_content = plist_content.replace('$4', custom_uuid)  # CustomUUID for Clover
                    logger.info(f"Legacy版本：已替换Board-ID和CustomUUID占位符")
                else:
                    logger.info(f"OpenCore版本：跳过Board-ID和CustomUUID占位符替换")

                # 生成plist文件
                plist_filename = f"{vm_name}.plist"
                plist_file_path = os.path.join(plist_chengpin_template_dir, plist_filename)
                os.makedirs(os.path.dirname(plist_file_path), exist_ok=True)

                with open(plist_file_path, 'w', encoding='utf-8') as f:
                    f.write(plist_content)

                logger.info(f"生成plist文件: {plist_file_path}")

                # 根据版本设置不同的上传路径
                if macos_version == 'macos10.15+':
                    remote_config_path = oc_config_path  # OpenCore路径
                    logger.info(f"macos10.15+版本，使用OpenCore配置路径: {remote_config_path}")
                else:
                    remote_config_path = boot_config_path  # Clover路径
                    logger.info(f"Legacy版本，使用Clover配置路径: {remote_config_path}")

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

                # 注意：重启进度在monitor_vm_and_configure函数中更新，这里不需要重复更新

                # 执行mount_efi.sh脚本
                script_path = f"{sh_script_remote_path}/mount_efi.sh"
                logger.info(f"执行mount脚本: {script_path}")
                success, output, ssh_log = execute_remote_script(vm_ip, vm_username, script_path)

                if not success:
                    logger.warning(f"mount_efi.sh执行失败: {output}")
                    # 继续执行，不中断流程
                else:
                    logger.info(f"mount_efi.sh执行成功")

                # 传输plist文件到虚拟机
                if not os.path.exists(plist_file_path):
                    log_message('error', f'plist文件不存在: {plist_file_path}')
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': f'plist文件不存在: {plist_file_path}'
                    })
                    continue

                success, message = send_file_via_sftp(plist_file_path, remote_config_path, vm_ip, vm_username,
                                                      timeout=60)

                if not success:
                    log_message('error', f'文件传输失败: {message}')
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': f'文件传输失败: {message}'
                    })
                    continue
                else:
                    logger.info(f"文件传输成功")

                # 备份已使用的五码
                config_filename = os.path.basename(config_file_path)
                config_filename = Path(config_filename).stem
                backup_config_file = os.path.join(backup_dir, f'{config_filename}_install.bak')

                # 追加到备份配置文件
                with open(backup_config_file, 'a', encoding='utf-8') as f:
                    f.write(wuma_line + '\n')

                used_wuma_lines.append(wuma_line)

                # 注意：五码进度在monitor_vm_and_configure函数中更新，这里不需要重复更新
                results.append({
                    'vm_name': vm_name,
                    'success': True,
                    'message': '批量更改五码成功'
                })

                log_message('success', f'虚拟机 {vm_name} 更改五码完成')

            except Exception as e:
                log_message('error', f'处理虚拟机 {vm_name} 时出错: {str(e)}')
                results.append({
                    'vm_name': vm_name,
                    'success': False,
                    'message': f'处理失败: {str(e)}'
                })

        # 五码已在分配时从配置文件中移除，这里只记录使用情况
        logger.info(f"本次使用了 {len(used_wuma_lines)} 个五码，剩余五码数量请查看配置文件")

        success_count = sum(1 for r in results if r['success'])
        total_count = len(results)

        log_message('info', f'更改五码完成 - 成功: {success_count}/{total_count}')

        return {
            'status': 'success',
            'message': f'更改五码完成！成功处理 {success_count}/{total_count} 个虚拟机',
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
    finally:
        # 确保清理锁文件
        try:
            busy_lock_path = lock_file_path + '.busy'
            if os.path.exists(busy_lock_path):
                os.remove(busy_lock_path)
                logger.debug(f"清理锁文件: {busy_lock_path}")
        except Exception as cleanup_error:
            logger.warning(f"清理锁文件时出错: {cleanup_error}")
