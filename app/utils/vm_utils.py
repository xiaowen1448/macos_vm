
import os
import subprocess
import paramiko
from datetime import datetime
import sys
import time
import base64
import uuid
import json
import threading
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from pathlib import Path
from functools import wraps
from config import *
from app.utils.common_utils import logger
from app.utils.ssh_utils import *
from app.utils.vnc_utils import *

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

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import *


# 注意：clear_sessions_on_startup不应在此处调用，而应在应用主入口处调用

VM_DIRS = {
    '10_12': clone_dir,
    'chengpin': vm_chengpin_dir
}
clone_tasks = {}
tasks = {}
websockify_processes = {}  # 存储websockify进程信息





def find_vmx_file_by_ip(target_ip):
    """根据IP地址查找对应的VMX文件"""
    try:
        vmrun_path = get_vmrun_path()

        # 首先获取运行中的虚拟机列表
        list_cmd = [vmrun_path, 'list']
        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')

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
                        #  logger.info(f"找到匹配IP {target_ip} 的VMX文件: {vm_path}")
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
        content, encoding = read_vmx_file_smart(vmx_path)
        if content is not None:
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




def find_vm_file(vm_name):
    """查找虚拟机文件"""
    try:
        # 如果vm_name已经是完整路径，直接检查是否存在
        if vm_name.endswith('.vmx') and os.path.exists(vm_name):
            return vm_name

        # 如果是完整路径但文件不存在，记录警告
        if vm_name.endswith('.vmx'):
            return None
            
        vm_dir = vm_base_dir
        if os.path.exists(vm_dir):
            # 首先尝试精确匹配
            for root, dirs, files in os.walk(vm_dir):
                for file in files:
                    if file.endswith('.vmx') and file == f"{vm_name}.vmx":
                        return os.path.join(root, file)
            
            # 如果精确匹配失败，尝试模糊匹配
            for root, dirs, files in os.walk(vm_dir):
                for file in files:
                    if file.endswith('.vmx') and vm_name.lower() in file.lower():
                        return os.path.join(root, file)
        return None

    except Exception as e:
        logger.error(f"查找虚拟机文件失败: {str(e)}")
        return None

def get_vm_ip(vm_name):
    """获取虚拟机IP地址，优先用vmrun getGuestIPAddress"""
    try:
        # 1. 通过vmrun getGuestIPAddress
        vm_file = find_vm_file(vm_name)
        if vm_file:
            vmrun_path = get_vmrun_path()
            
            if os.path.exists(vmrun_path):
                try:
                    cmd = [vmrun_path, 'getGuestIPAddress', vm_file, '-wait']
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 4294967295:
                        return None

                    if result.returncode == 0:
                        ip = result.stdout.strip()
                        if is_valid_ip(ip):
                            return ip
                        else:
                            logger.warning(f"vmrun返回的IP格式无效: {ip}")
                    else:
                        logger.warning(f"vmrun命令执行失败，返回码: {result.returncode}, 错误: {result.stderr}")
                except Exception as e:
                    logger.error(f"未获取IP地址,虚拟机正在启动中!")
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
                            if is_valid_ip(ip):
                                return ip
                            else:
                                logger.warning(f"VMX文件中的IP格式无效: {ip}")
            except Exception as e:
                logger.error(f"从VMX文件读取IP失败: {str(e)}")

       # logger.warning(f"无法获取虚拟机 {vm_name} 的IP地址")
        return None
    except Exception as e:
        logger.error(f"获取虚拟机IP失败: {str(e)}")
        return None



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
                logger.info(f"[DEBUG] 发送监控进度更新: {progress_data}")
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

                # 检测IP存活
                if not ping_vm_ip(vm_ip):
                    add_task_log(task_id, 'debug', f'虚拟机 {vm_name} ({vm_ip}) ping不通，等待5秒后重试...')
                    time.sleep(5)
                    continue

                if not check_ssh_connectivity(vm_ip, vm_username):
                    add_task_log(task_id, 'debug', f'虚拟机 {vm_name} ({vm_ip}) SSH未就绪，等待10秒后重试...')
                    time.sleep(10)
                    continue
                try:
                        add_task_log(task_id, 'info', f'开始为虚拟机 {vm_name} 配置五码...')
                        result = batch_change_wuma_core([vm_name], wuma_config_file, task_id)

                        if isinstance(result, dict) and result.get('status') == 'success':
                            add_task_log(task_id, 'success', f'虚拟机 {vm_name} 五码配置成功')
                            add_task_log(task_id, 'info', f'开始为虚拟机 {vm_name} 执行JU值更改')
                            logger.info(f"[DEBUG] 开始为虚拟机 {vm_name} 执行JU值更改")
                        else:
                            error_msg = result.get('message', '未知错误') if isinstance(result, dict) else '配置失败'
                            add_task_log(task_id, 'error', f'虚拟机 {vm_name} 五码配置失败: {error_msg}')
                            logger.info(f"[DEBUG] 虚拟机 {vm_name} 五码配置失败: {error_msg}")
                            update_monitoring_progress(failed=True)

                            # 检查是否所有虚拟机都已完成监控
                            check_and_complete_task(task_id)
                            return False

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
                            add_task_log(task_id, 'info', f'执行test.sh脚本更改虚拟机 {vm_name} 的JU值')
                            script_path = f"{sh_script_remote_path}test.sh"
                            success, output, ssh_log = execute_remote_script(vm_ip, vm_username, script_path)
                            if success:
                                add_task_log(task_id, 'debug', f'JU值更改脚本输出: {output}')
                                add_task_log(task_id, 'success', f'虚拟机 {vm_name} JU值更改成功')
                                add_task_log(task_id, 'info', f'开始重启虚拟机 {vm_name}...')
                                logger.info(f"[DEBUG] 开始重启虚拟机 {vm_name}")
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
                                    add_task_log(task_id, 'info', f'执行虚拟机 {vm_name} 重启命令，超时设置为200秒')
                                    add_task_log(task_id, 'debug', f'重启命令: {" ".join(reset_cmd)}')
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
                                add_task_log(task_id, 'debug', f'JU值更改失败详情: {ssh_log}')
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
    """检查SSH连通性 - 使用app.utils.ssh_utils中的实现"""
    try:
        # 从app.utils.ssh_utils导入check_ssh_connectivity函数
        from app.utils.ssh_utils import check_ssh_connectivity as ssh_check_connectivity
        return ssh_check_connectivity(ip_address, username, timeout=timeout)
    except Exception as e:
        logger.error(f"调用SSH连通性检查失败: {str(e)}")
        return False

def check_ssh_connectivity_old(ip_address, username, timeout=10):
    """旧的SSH连通性检测实现（已弃用）"""
    try:
        # 使用新的SSH工具类实现
        from app.utils.ssh_utils import check_ssh_connectivity as new_check_ssh_connectivity
        return new_check_ssh_connectivity(ip_address, username, timeout=timeout)
    except Exception as e:
        logger.error(f"调用SSH连通性检查失败: {str(e)}")
        return False

def get_vmrun_path():
    """获取vmrun工具路径"""
    try:
        from ..config import vmrun_path
        return vmrun_path
    except ImportError:
        # 默认路径
        default_path = "C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe"
        return default_path



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



# 克隆后等待执行更改五码的操作
def batch_change_wuma_core(selected_vms, config_file_path, task_id=None):
    """批量更改五码核心函数"""
    logger.info(f"开始批量更改五码核心处理，虚拟机数量: {len(selected_vms)}")
    logger.info(f"使用配置文件: {config_file_path}")
    # 添加任务日志记录
    if task_id:
        add_task_log(task_id, 'info', f'开始批量更改五码配置，虚拟机数量: {len(selected_vms)}，配置文件: {config_file_path}')

    def log_message(level, message):
        """统一日志记录函数"""
        # 根据不同级别记录日志到logger
        if level == 'debug':
            logger.debug(message)
        elif level == 'info':
            logger.info(message)
        elif level == 'warning':
            logger.warning(message)
        elif level == 'error':
            logger.error(message)
        elif level == 'success':
            logger.info(message)
        # 添加到任务日志
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
            
            log_message('debug', f'分配五码中，为{len(selected_vms)}个虚拟机分配{len(allocated_wuma_lines)}个五码')
            
            # 立即更新配置文件，移除已分配的五码
            with open(config_file_path, 'w', encoding='utf-8') as f:
                for line in remaining_wuma_lines:
                    f.write(line + '\n')
            
            log_message('info', f'已分配 {len(allocated_wuma_lines)} 个五码，剩余 {len(remaining_wuma_lines)} 个')
            log_message('debug', f'已从配置文件中移除已分配的五码')

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
        log_message('debug', '开始验证选中的虚拟机运行状态')
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
            log_message('debug', f'检查虚拟机 {vm_name} 是否在运行中')
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
                  #  logger.info(f"ROM原始值: {rom}, PowerShell风格字节: {rom_bytes}, base64加密后: {rom_base64}, 格式化后: {rom_formatted}")
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
                 #   log_message('error', f'无法获取虚拟机 {vm_name} 的IP')
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




def batch_change_ju_worker(task_id, selected_vms):
    """批量更改JU值后台工作函数"""
    logger.info(f"开始批量更改JU值任务: {task_id}")
    
    # 初始化任务结果结构
    tasks[task_id] = {
        'status': 'running',
        'current': 0,
        'progress': 0,
        'results': [],
        'logs': []
    }

    try:
        # 验证选中的虚拟机是否都在运行
        vmrun_path = get_vmrun_path()

        list_cmd = [vmrun_path, 'list']

        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=60, encoding='utf-8', errors='ignore')

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
                        'message': f'test.sh脚本执行失败: {output}'
                    })
                    continue

                add_task_log(task_id, 'INFO', f'test.sh脚本执行成功: {vm_name}')

                # 重启虚拟机
                add_task_log(task_id, 'INFO', f'开始重启虚拟机: {vm_name}')
                restart_cmd = [vmrun_path, 'reset', vm_path]
                logger.info(f"重启虚拟机: {restart_cmd}")
                try:
                    subprocess.run(restart_cmd, capture_output=True, timeout=60)
                except subprocess.TimeoutExpired:
                    logger.warning(f"重启虚拟机 {vm_name} 超时，但可能仍在进行中")
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

            except subprocess.TimeoutExpired as e:
                logger.error(f"处理虚拟机 {vm_name} 时超时: {str(e)}")
                add_task_log(task_id, 'ERROR', f'处理虚拟机 {vm_name} 时超时: {str(e)}')
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
        add_task_log(task_id, 'info', f'找到有效五码数量: {len(wuma_codes)}')

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
            add_task_log(task_id, 'warning', warning_msg)
            logger.info(f"[DEBUG] 警告: {warning_msg}")
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
        logger.info(f"[DEBUG] 获取五码信息失败: {str(e)}")
        return None



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
    # 确保logs_dir已正确导入（从config模块导入）
    global logs_dir
    
    task = None
    # 首先检查是否在tasks字典中
    if task_id in tasks:
        task = tasks[task_id]
        # 确保logs列表存在
        if 'logs' not in task:
            task['logs'] = []
    # 然后检查是否在clone_tasks字典中
    elif task_id in clone_tasks:
        task = clone_tasks[task_id]
    
    # 如果找到任务，添加日志
    if task:
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message
        }
        task['logs'].append(log_entry)
        sys.stdout.flush()
        
        # 同时写入日志文件
        current_date = datetime.now().strftime('%Y-%m-%d')
        log_file_path = os.path.join(logs_dir, f'task_{task_id}_{current_date}.log')
        try:
            with open(log_file_path, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f'[{timestamp}] [{level.upper()}] {message}\n')
                f.flush()  # 强制刷新文件缓冲区
        except Exception as e:
            logger.info(f"[DEBUG] 写入日志文件失败: {str(e)}")


# 通用函数 - 扫描脚本文件
def scan_scripts_from_directories():
    """从配置的多个目录递归扫描脚本文件"""
    scripts = []

    # 使用新的多目录配置
    for scripts_dir in script_upload_dirs:
        if os.path.exists(scripts_dir):
            logger.debug(f"递归扫描脚本目录: {scripts_dir}")
            # 使用os.walk递归遍历所有子目录
            for root, _, files in os.walk(scripts_dir):
                for filename in files:
                    # 支持.sh和.scpt文件
                    if filename.endswith('.sh') or filename.endswith('.scpt'):
                        file_path = os.path.join(root, filename)
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
                        except Exception as e:
                            logger.error(f"处理脚本文件 {file_path} 时出错: {str(e)}")
                            continue
        else:
            logger.warning(f"脚本目录不存在: {scripts_dir}")

    # 按文件名排序
    scripts.sort(key=lambda x: x['name'])
    return scripts


# 通用函数 - 获取虚拟机列表
def get_vm_list_from_directory(vm_dir, vm_type_name):
    """从指定目录获取虚拟机列表"""
    global logger
    # logger.info(f"收到获取{vm_type_name}虚拟机列表API请求")
    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        get_all = request.args.get('all', 'false').lower() == 'true'  # 新增获取所有数据参数
        logger.debug(f"分页参数 - 页码: {page}, 每页大小: {page_size}, 获取所有: {get_all}")

        vms = []
        stats = {'total': 0, 'running': 0, 'stopped': 0, 'suspended': 0, 'online': 0}

        logger.debug(f"开始扫描{vm_type_name}虚拟机目录: {vm_dir}")
        running_vms = set()
        try:
            vmrun_path = get_vmrun_path()

            list_cmd = [vmrun_path, 'list']

            result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30, encoding='utf-8',
                                    errors='ignore')

            if result.returncode == 0:
                running_vms = set(result.stdout.strip().split('\n')[1:])  # 跳过标题行
                # logger.debug(f"获取到运行中虚拟机: {len(running_vms)} 个")
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

                        # 获取创建时间
                        try:
                            create_time = os.path.getmtime(vm_path)
                        except Exception as e:
                          #  logger.warning(f"无法获取虚拟机 {vm_name} 的创建时间: {str(e)}")
                            create_time = 0

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
                            'vm_status': vm_status,  # 添加虚拟机状态字段
                            'create_time': create_time  # 添加创建时间字段
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
        # 排序逻辑：开机虚拟机排在最前面，未开机的按创建时间倒序排列
        vms.sort(key=lambda vm: (vm['status'] != 'running', -vm['create_time']))
        # 计算分页
        total_count = len(vms)

        if get_all:
            # 返回所有数据，不分页
            paged_vms = vms
            total_pages = 1
            start_index = 0
            end_index = total_count
        else:
            # 正常分页
            total_pages = (total_count + page_size - 1) // page_size
            start_index = (page - 1) * page_size
            end_index = min(start_index + page_size, total_count)
            paged_vms = vms[start_index:end_index] if vms else []

        logger.info(
            f"{vm_type_name}虚拟机列表获取完成 - 总数: {total_count}, 运行中: {stats['running']}, 已停止: {stats['stopped']}, 挂起: {stats['suspended']}")

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
    global logger
    #  logger.info(f"收到获取{vm_type_name}虚拟机五码信息请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')

        if not vm_name:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称参数'
            })

        # 首先检查缓存
        cached_result = vm_cache.get_cached_status(vm_name, 'wuma_info')
        if cached_result:
            # logger.debug(f"使用缓存的五码信息: {vm_name}")
            return jsonify(cached_result)

        # 获取虚拟机IP（不执行强制重启）
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            return jsonify({
                'success': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址，请先启动虚拟机'
            })

        # 执行远程脚本获取五码信息
        result = execute_remote_script(vm_ip, 'wx', f'{sh_script_remote_path}run_debug_wuma.sh')
        if len(result) == 3:
            success, output, ssh_log = result
        elif len(result) == 2:
            success, output = result
        else:
            success, output = False, "未知错误"

        if success:
            result_data = {
                'success': True,
                'output': output
            }
            # 缓存成功结果
            vm_cache.set_cached_status(vm_name, result_data, 'wuma_info')
            return jsonify(result_data)
        else:
            result_data = {
                'success': False,
                'error': output
            }
            # 失败结果不缓存或使用较短缓存时间
            return jsonify(result_data)
    except Exception as e:
        logger.error(f"获取{vm_type_name}虚拟机五码信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取{vm_type_name}虚拟机五码信息失败: {str(e)}'
        })


# 通用函数 - 获取JU值信息
def get_ju_info_generic(vm_type_name):
    """获取虚拟机JU值信息的通用函数"""
    global logger
    # logger.info(f"收到获取{vm_type_name}虚拟机JU值信息请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')

        if not vm_name:
            return jsonify({
                'success': False,
                'message': '缺少虚拟机名称参数'
            })

        # 首先检查缓存
        cached_result = vm_cache.get_cached_status(vm_name, 'ju_info')
        if cached_result:
            # logger.debug(f"使用缓存的JU值信息: {vm_name}")
            return jsonify(cached_result)

        # 获取虚拟机IP（不执行强制重启）
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            return jsonify({
                'success': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址，请先启动虚拟机'
            })

        # 执行远程脚本获取JU值信息
        result = execute_remote_script(vm_ip, 'wx', f'{sh_script_remote_path}run_debug_ju.sh')
        if len(result) == 3:
            success, output, ssh_log = result
        elif len(result) == 2:
            success, output = result
        else:
            success, output = False, "未知错误"

        if success:
            result_data = {
                'success': True,
                'output': output
            }
            # 缓存成功结果
            vm_cache.set_cached_status(vm_name, result_data, 'ju_info')
            return jsonify(result_data)
        else:
            result_data = {
                'success': False,
                'error': output
            }
            # 失败结果不缓存或使用较短缓存时间
            return jsonify(result_data)
    except Exception as e:
        logger.error(f"获取{vm_type_name}虚拟机JU值信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取{vm_type_name}虚拟机JU值信息失败: {str(e)}'
        })


# 通用函数 - 虚拟机操作（启动、停止、重启）
def vm_operation_generic(operation, vm_type_name, vm_dir):
    """虚拟机操作的通用函数"""
    global logger
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

        # logger.info(f"执行{operation}命令: {cmd}")

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
                'failed_vms': []  # 删除失败的虚拟机列表
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
    # logger.info(f"收到获取{vm_type_name}虚拟机详细信息请求: {vm_name}")
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

            # 确保脚本名以.sh结尾
            if script_name.endswith('.sh'):
                dir_script_remote_path = sh_script_remote_path
            else:
                dir_script_remote_path = scpt_script_remote_path
            # 列出指定脚本的权限

            # 使用SFTP发送脚本
            remote_file_path = f"{dir_script_remote_path}{script_name}"
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
    # logger.info(f"收到获取{vm_type_name}虚拟机IP状态请求: {vm_name}")
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


def get_vm_name_by_ip(ip):
    """根据IP地址获取虚拟机名称"""
    try:
        # 遍历所有虚拟机，找到匹配的IP
        vm_dirs = [clone_dir, vm_chengpin_dir]
        for vm_dir in vm_dirs:
            if os.path.exists(vm_dir):
                for vm_name in os.listdir(vm_dir):
                    vm_path = os.path.join(vm_dir, vm_name)
                    if os.path.isdir(vm_path):
                        vm_ip = get_vm_ip(vm_name)
                        if vm_ip == ip:
                            return vm_name
        return None
    except Exception as e:
        logger.error(f"根据IP获取虚拟机名称失败: {str(e)}")
        return None


def get_vm_online_status(vm_name):
    """获取虚拟机在线状态（新逻辑：根据虚拟机状态和网络连接情况综合判断）"""
    # logger.debug(f"检查虚拟机 {vm_name} 的在线状态（新逻辑）")

    # 首先检查缓存
    cached_status = vm_cache.get_cached_status(vm_name, 'online_status')
    if cached_status:
        return cached_status

    try:
        vm_file = find_vm_file(vm_name)
        if not vm_file:
            result = {
                'status': 'offline',
                'reason': '虚拟机文件不存在',
                'ip': None,
                'ssh_trust': False,
                'ssh_port_open': False,
                'vm_status': 'unknown'
            }
            # 缓存结果（较短时间，因为文件可能会被创建）
            vm_cache.set_cached_status(vm_name, result, 'online_status')
            return result

        vm_status = get_vm_status(vm_file)
        if vm_status == 'stopped':
            # logger.debug(f"虚拟机 {vm_name} 已关机")
            result = {
                'status': 'offline',
                'reason': '虚拟机关机',
                'ip': None,
                'ssh_trust': False,
                'ssh_port_open': False,
                'vm_status': vm_status
            }
            # 缓存结果
            vm_cache.set_cached_status(vm_name, result, 'online_status')
            return result
        elif vm_status in ['suspended', 'paused']:
            # logger.debug(f"虚拟机 {vm_name} 处于挂起状态")
            result = {
                'status': 'unknown',
                'reason': f'虚拟机{vm_status}状态',
                'ip': None,
                'ssh_trust': False,
                'ssh_port_open': False,
                'vm_status': vm_status
            }
            # 缓存结果
            vm_cache.set_cached_status(vm_name, result, 'online_status')
            return result
        elif vm_status == 'unknown':
            logger.debug(f"虚拟机 {vm_name} 状态未知，继续检查网络连接")
            # 状态未知时，继续检查网络连接情况
        elif vm_status != 'running':
            # logger.debug(f"虚拟机 {vm_name} 状态异常: {vm_status}")
            result = {
                'status': 'unknown',
                'reason': f'虚拟机状态异常: {vm_status}',
                'ip': None,
                'ssh_trust': False,
                'ssh_port_open': False,
                'vm_status': vm_status
            }
            # 缓存结果
            vm_cache.set_cached_status(vm_name, result, 'online_status')
            return result

        # 3. 虚拟机运行中或状态未知，检查网络连接情况
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            result = {
                'status': 'unknown',
                'reason': '无法获取IP地址',
                'ip': None,
                'ssh_trust': False,
                'ssh_port_open': False,
                'vm_status': vm_status
            }
            # 缓存结果（较短时间，因为IP可能很快就能获取到）
            vm_cache.set_cached_status(vm_name, result, 'online_status')
            return result
            # 4. 检查IP连通性
        ip_status = check_ip_connectivity(vm_ip)
        # logger.info(f"[DEBUG] 虚拟机 {vm_name} IP连通性检查结果: {ip_status}")
        if not ip_status['success']:
            result = {
                'status': 'offline',
                'reason': f'IP不可达: {ip_status.get("error", "未知错误")}',
                'ip': vm_ip,
                'ssh_trust': False,
                'ssh_port_open': False,
                'vm_status': vm_status
            }
            # 缓存结果
            vm_cache.set_cached_status(vm_name, result, 'online_status')
            return result

        # 5. 检查SSH端口是否开放
        ssh_port_open = check_ssh_port_open(vm_ip)
        ssh_trust_status = check_ssh_trust_status(vm_ip, vm_username)
        conditions_met = 0
        total_conditions = 3

        if ip_status['success']:
            conditions_met += 1
        if ssh_port_open:
            conditions_met += 1
        if ssh_trust_status:
            conditions_met += 1

        if conditions_met == total_conditions:
            # 三个条件都满足：完全在线
            status_text = '完全在线'
            reason_text = 'IP可达 + SSH端口开放 + SSH互信成功'
            if vm_status == 'unknown':
                status_text = '完全在线（状态未知）'
                reason_text = 'IP可达 + SSH端口开放 + SSH互信成功（虚拟机状态未知）'

            result = {
                'status': 'online',
                'reason': reason_text,
                'ip': vm_ip,
                'ssh_trust': True,
                'ssh_port_open': True,
                'vm_status': vm_status
            }
            # 缓存结果
            vm_cache.set_cached_status(vm_name, result, 'online_status')
            return result
        elif conditions_met > 0:
            # 部分条件满足：部分在线
            missing_conditions = []
            if not ip_status['success']:
                missing_conditions.append('IP不可达')
            if not ssh_port_open:
                missing_conditions.append('SSH端口未开放')
            if not ssh_trust_status:
                missing_conditions.append('SSH互信未设置')
            reason = f'部分在线（缺少: {", ".join(missing_conditions)}）'
            if vm_status == 'unknown':
                status_text = '部分在线（状态未知）'
                reason = f'部分在线（缺少: {", ".join(missing_conditions)}，虚拟机状态未知）'

            #  logger.debug(f"虚拟机 {vm_name} {reason}")
            result = {
                'status': 'partial',
                'reason': reason,
                'ip': vm_ip,
                'ssh_trust': ssh_trust_status,
                'ssh_port_open': ssh_port_open,
                'vm_status': vm_status
            }
            # 缓存结果
            vm_cache.set_cached_status(vm_name, result, 'online_status')
            return result
        else:
            # 没有条件满足：未在线
            status_text = '未在线'
            reason_text = '所有网络条件都不满足'
            if vm_status == 'unknown':
                status_text = '未在线（状态未知）'
                reason_text = '所有网络条件都不满足（虚拟机状态未知）'

            #  logger.debug(f"虚拟机 {vm_name} {status_text}：{reason_text}")
            result = {
                'status': 'offline',
                'reason': reason_text,
                'ip': vm_ip,
                'ssh_trust': False,
                'ssh_port_open': False,
                'vm_status': vm_status
            }
            # 缓存结果
            vm_cache.set_cached_status(vm_name, result, 'online_status')
            return result

    except Exception as e:
        # logger.error(f"检查虚拟机 {vm_name} 在线状态时出错: {str(e)}")
        return {
            'status': 'error',
            'reason': f'检查状态时出错: {str(e)}',
            'ip': None,
            'ssh_trust': False,
            'ssh_port_open': False,
            'vm_status': 'unknown'
        }



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
        logger.info(f"[DEBUG] 获取快照列表失败: {str(e)}")
        return []


def read_vmx_file_smart(vmx_file_path):
    """智能编码读取vmx文件的通用函数"""
    encodings_to_try = ['utf-8', 'gbk', 'ansi', 'cp1252']

    for encoding in encodings_to_try:
        try:
            with open(vmx_file_path, 'r', encoding=encoding) as f:
                content = f.read()
            logger.debug(f"成功使用 {encoding} 编码读取vmx文件: {vmx_file_path}")
            return content, encoding
        except UnicodeDecodeError:
            logger.debug(f"使用 {encoding} 编码读取失败，尝试下一种编码")
            continue
        except Exception as e:
            logger.error(f"读取vmx文件时出错: {str(e)}")
            return None, None

    logger.error(f"无法使用任何编码读取vmx文件: {vmx_file_path}")
    return None, None


def get_vm_config(vm_path):
    """获取虚拟机配置信息"""
    try:
        content, encoding = read_vmx_file_smart(vm_path)
        if content is None:
            logger.info(f"[DEBUG] 获取虚拟机配置失败: 无法读取文件")
            return {}

        config = {}
        for line in content.split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip().strip('"')

        return config

    except Exception as e:
        logger.info(f"[DEBUG] 获取虚拟机配置失败: {str(e)}")
        return {}


def get_vm_status(vm_path):
    """获取虚拟机状态"""
    try:
        vmrun_path = get_vmrun_path()

        # logger.info(f"[DEBUG] 使用vmrun路径: {vmrun_path}")
        list_cmd = [vmrun_path, 'list']
        # logger.info(f"[DEBUG] 执行命令: {' '.join(list_cmd)}")

        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')

        # logger.info(f"[DEBUG] vmrun list命令返回码: {result.returncode}")
        # logger.info(f"[DEBUG] vmrun list命令输出: {result.stdout}")
        if result.stderr:
            logger.info(f"[DEBUG] vmrun list命令错误: {result.stderr}")

        if result.returncode == 0:
            running_vms = result.stdout.strip().split('\n')[1:]  # 跳过标题行
            vm_name = os.path.splitext(os.path.basename(vm_path))[0]
            # logger.info(f"[DEBUG] 查找虚拟机名称: {vm_name}")
            # logger.info(f"[DEBUG] 运行中的虚拟机列表: {running_vms}")

            # 检查虚拟机是否在运行列表中
            vm_found = False
            for vm in running_vms:
                if vm.strip() and vm_name in vm:
                    # logger.info(f"[DEBUG] 找到运行中的虚拟机: {vm}")
                    vm_found = True
                    break

            if vm_found:
                # 检查虚拟机是否正在启动过程中
                try:
                    # 尝试获取虚拟机IP，如果获取失败可能正在启动
                    # 对于母盘虚拟机，直接使用vmrun getGuestIPAddress命令
                    vmrun_path = get_vmrun_path()
                    cmd = [vmrun_path, 'getGuestIPAddress', vm_path, '-wait']
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                    if result.returncode == 0:
                        vm_ip = result.stdout.strip()
                        if vm_ip and is_valid_ip(vm_ip):
                            return 'running'
                        else:
                            return 'starting'
                    else:
                        return 'starting'
                except Exception as e:
                    return 'starting'
            else:
                # 虚拟机不在运行列表中，检查是否处于挂起状态
                # logger.info(f"[DEBUG] 未找到运行中的虚拟机: {vm_name}，检查是否挂起")

                # 检查.vmss文件是否存在（挂起状态文件）
                vm_dir = os.path.dirname(vm_path)
                vmss_files = [f for f in os.listdir(vm_dir) if f.endswith('.vmss')]
                if vmss_files:
                    # logger.info(f"[DEBUG] 发现挂起状态文件: {vmss_files}")
                    return 'suspended'

                return 'stopped'

        return 'stopped'

    except Exception as e:
        # logger.info(f"[DEBUG] 获取虚拟机状态失败: {str(e)}")
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



def get_vm_ip_status(vm_name):
    """获取虚拟机IP状态信息"""
    # logger.debug(f"开始获取虚拟机 {vm_name} 的IP状态")
    try:
        ip = get_vm_ip(vm_name)
        if not ip:
            # logger.warning(f"虚拟机 {vm_name} 未获取到IP地址")
            return {
                'ip': None,
                'status': 'no_ip',
                'message': '未获取到IP地址'
            }

        # logger.debug(f"虚拟机 {vm_name} IP地址: {ip}")

        # 检查IP连通性
        ping_result = check_ip_connectivity(ip)

        if ping_result['success']:
            #  logger.info(f"虚拟机 {vm_name} IP {ip} 可达")
            return {
                'ip': ip,
                'status': 'online',
                'message': 'IP地址可达',
                'response_time': ping_result.get('response_time')
            }
        else:
            # logger.warning(f"虚拟机 {vm_name} IP {ip} 不可达: {ping_result.get('error')}")
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
    # logger.debug(f"开始检查IP连通性: {ip}")
    try:
        # 使用ping命令检查连通性
        ping_cmd = ['ping', '-n', '1', '-w', '3000', ip]
        # logger.debug(f"执行ping命令: {ping_cmd}")
        result = subprocess.run(ping_cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            # 解析响应时间
            response_time = None
            for line in result.stdout.split('\n'):
                if '时间=' in line or 'time=' in line.lower():
                    try:
                        time_str = line.split('时间=')[1].split('ms')[0].strip()
                        response_time = int(time_str)
                    #  logger.debug(f"解析到响应时间: {response_time}ms")
                    except:
                        # logger.debug("响应时间解析失败")
                        pass
                    break

            # logger.debug(f"IP {ip} 连通性检查成功，响应时间: {response_time}ms")
            return {
                'success': True,
                'response_time': response_time
            }
        else:
            # logger.warning(f"IP {ip} ping失败，返回码: {result.returncode}")
            return {
                'success': False,
                'error': 'ping失败'
            }

    except subprocess.TimeoutExpired:
        # logger.error(f"IP {ip} 连接超时")
        return {
            'success': False,
            'error': '连接超时'
        }
    except Exception as e:
        # logger.error(f"IP {ip} 连通性检查异常: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
