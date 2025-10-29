from flask import Blueprint, jsonify, request, render_template
from datetime import datetime
import os
import json
import requests
import subprocess
import time
import threading
import shutil
import logging
import sqlite3
import socket
from pathlib import Path
# 导入配置模块，使用appleid_unused_dir路径和其他配置项
from config import appleid_unused_dir, icloud_txt_path, restart_scptRunner, icloud2_txt_path, error_txt_path, vm_username
# 导入SSH工具类
from app.utils.ssh_utils import SSHClient

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('icloud_process')

# 创建蓝图
icloud_process_bp = Blueprint('icloud_process', __name__)

# 导入带session超时检查的login_required装饰器
from app.utils.common_utils import login_required

# 配置项
SCRIPT_DIR = restart_scptRunner
SCPTRUNNER_PORT = 8787
# 从config模块导入的路径配置
ICLOUD_TXT_PATH = icloud_txt_path
ICLOUD2_TXT_PATH = icloud2_txt_path
ERROR_TXT_PATH = error_txt_path
TEMP_PLIST_PATH = os.path.join(os.environ.get('TEMP', '/tmp'), 'temp_plist.txt')
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'logs'))

# 确保日志目录存在
os.makedirs(LOG_DIR, exist_ok=True)

# 进程列表数据存储
processes = []

# 正在运行的进程任务
running_tasks = {}

# 存储进程输出日志的字典（用于兼容旧版本）
process_output_logs = {}

# 启动线程清理后台任务
def start_thread_cleanup_task():
    """启动一个后台线程，定期清理已结束的线程"""
    def cleanup_threads():
        while True:
            try:
                # 获取所有需要清理的进程ID
                to_remove = []
                for process_id, thread in running_tasks.items():
                    if not thread.is_alive():
                        to_remove.append(process_id)
                
                # 移除已结束的线程
                for process_id in to_remove:
                    logger.info(f'[INFO] 清理已结束的线程 - 进程ID: {process_id}')
                    del running_tasks[process_id]
                    # 同时更新对应进程的状态（如果需要）
                    for p in processes:
                        if p['id'] == process_id and p['status'] in ['启动中', '执行中']:
                            p['status'] = '已停止'
                            update_process_status(process_id, '已停止')
                            break
            except Exception as e:
                logger.error(f'[ERROR] 清理线程时发生异常: {str(e)}')
            
            # 每60秒执行一次清理
            time.sleep(60)
    
    # 创建并启动清理线程
    cleanup_thread = threading.Thread(target=cleanup_threads, daemon=True)
    cleanup_thread.start()
    logger.info(f'[INFO] 线程清理后台任务已启动')

# 启动线程清理任务
start_thread_cleanup_task()

# 获取VM信息路由已移至vm.py文件中

def get_db_connection():
    """获取数据库连接"""
    # 使用绝对路径确保数据库文件正确创建
    db_dir = Path(__file__).parent.parent.parent / 'db'
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / 'apple_ids.db'
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 创建apple_ids表（如果不存在）
    c.execute('''
        CREATE TABLE IF NOT EXISTS apple_ids
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         apple_id TEXT NOT NULL,
         status TEXT NOT NULL DEFAULT 'inactive',
         create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
    ''')
    
    # 创建processes表（如果不存在）
    c.execute('''
        CREATE TABLE IF NOT EXISTS processes
        (id TEXT PRIMARY KEY,
         name TEXT NOT NULL,
         client TEXT NOT NULL,
         apple_id_filename TEXT NOT NULL,
         apple_id_count INTEGER NOT NULL DEFAULT 0,
         status TEXT NOT NULL DEFAULT '已停止',
         create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
    ''')
    
    # 检查并添加scripts列（如果不存在）
    try:
        c.execute("PRAGMA table_info(processes)")
        columns = [column[1] for column in c.fetchall()]
        if 'scripts' not in columns:
            logger.info("添加scripts列到processes表...")
            c.execute("ALTER TABLE processes ADD COLUMN scripts TEXT")
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"更新数据库表结构时出错: {str(e)}")
    
    conn.commit()
    return conn

def sync_process_list_from_db():
    """从数据库同步进程列表到内存中"""
    global processes
    try:
        conn = get_db_connection()
        c = conn.cursor()
        # 获取所有进程
        c.execute('SELECT id, name, client, apple_id_filename, status, create_time FROM processes')
        db_processes = []
        for row in c.fetchall():
            apple_id_filename = row[3] if row[3] is not None else ''
            process_info = {
                'id': row[0],
                'name': row[1],
                'client': row[2],
                'apple_id': apple_id_filename,
                'file_name': apple_id_filename.split('/')[-1].split('\\')[-1] if apple_id_filename else '',
                'status': row[4],
                'create_time': row[5] if row[5] else time.strftime('%Y-%m-%d %H:%M:%S'),
                'apple_id_count': 0,
                'file_count': 0
            }
            
            # 统计Apple ID数量
            try:
                from config import appleid_unused_dir
                file_path = os.path.join(appleid_unused_dir, apple_id_filename)
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        apple_id_count = sum(1 for line in f if line.strip())
                    process_info['apple_id_count'] = apple_id_count
                    process_info['file_count'] = apple_id_count
            except Exception as e:
                logger.error(f"统计Apple ID数量时出错: {str(e)}")
                
            db_processes.append(process_info)
        conn.close()
        
        # 更新内存中的进程列表
        processes = db_processes
        logger.info(f"进程列表从数据库同步完成，当前内存中有{len(processes)}个进程")
    except Exception as e:
        logger.error(f"同步进程列表时发生异常: {str(e)}")

@icloud_process_bp.route('/api/script/list', methods=['GET'])
def get_script_list():
    try:
        # 从config.py中获取脚本目录配置
        import config
        script_dir = config.macos_script_dir
        
        # 确保目录存在
        if not os.path.exists(script_dir):
            return jsonify({'success': False, 'message': f'脚本目录不存在: {script_dir}'})
        
        # 获取目录下所有的.scpt文件
        scpt_files = []
        for file in os.listdir(script_dir):
            if file.endswith('.scpt'):
                file_path = os.path.join(script_dir, file)
                file_size = os.path.getsize(file_path)  # 获取文件大小
                scpt_files.append({
                    'name': file,
                    'path': file_path,
                    'size': file_size,
                    'filename': file  # 为了与前端兼容性
                })
        
        # 按照文件名排序
        scpt_files.sort(key=lambda x: x['name'])
        
        return jsonify({'success': True, 'data': scpt_files})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取脚本列表失败: {str(e)}'})


# 辅助函数：从文件中读取Apple ID内容
def read_apple_id_file(file_name):
    """
    从appleid_unused_dir目录读取Apple ID文件内容
    """
    if not file_name:
        return None
    
    try:
        # 使用配置文件中的appleid_unused_dir路径
        file_path = os.path.join(appleid_unused_dir, file_name)
        if os.path.exists(file_path):
            logger.info(f'[INFO] 从{appleid_unused_dir}读取文件: {file_name}')
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        else:
            logger.warning(f'[WARNING] 文件不存在: {file_path}')
            return None
    except Exception as e:
        logger.error(f'[ERROR] 读取文件时出错: {str(e)}')
        return None

# 辅助函数：统计有效Apple ID数量
def count_valid_apple_ids(apple_id_text_or_file):
    """
    统计有效Apple ID数量，与前端保持一致的验证逻辑
    每行必须能被'----'分割成至少4个部分才视为有效
    
    如果输入是文件名，则从appleid_unused_dir目录读取文件内容
    如果输入是文本内容，则直接处理
    """
    file_name = None
    
    # 确定是文件名还是文本内容
    if isinstance(apple_id_text_or_file, str):
        # 检查是否是文件名（不包含换行符，且可能是文件名格式）
        if '\n' not in apple_id_text_or_file and ('.txt' in apple_id_text_or_file or len(apple_id_text_or_file) < 100):
            # 尝试作为文件名读取
            file_name = apple_id_text_or_file
            apple_id_text = read_apple_id_file(file_name)
            if apple_id_text is None:
                # 如果文件不存在，尝试将输入作为文本内容处理
                apple_id_text = apple_id_text_or_file
        else:
            # 作为文本内容处理
            apple_id_text = apple_id_text_or_file
            # 提取文件名（如果输入包含路径）
            if '/' in apple_id_text or '\\' in apple_id_text:
                file_name = apple_id_text.split('/')[-1].split('\\')[-1]
            else:
                file_name = apple_id_text[:50] if apple_id_text else None
    else:
        apple_id_text = None
    
    if not apple_id_text:
        return 0, file_name
    
    # 分割文本并统计有效行
    apple_ids = apple_id_text.strip().split('\n')
    valid_apple_ids = []
    
    for idx, line in enumerate(apple_ids, 1):
        line_stripped = line.strip()
        if line_stripped:
            parts = line_stripped.split('----')
            if len(parts) >= 4:
                valid_apple_ids.append(line_stripped)
    
    apple_id_count = len(valid_apple_ids)
    return apple_id_count, file_name

# 辅助函数：计算总Apple ID数量（icloud.txt和icloud2.txt的总和）
def calculate_total_apple_ids(vm_ip, temp_plist_path=TEMP_PLIST_PATH):
    """计算总Apple ID数量，包括未处理(icloud.txt)和已处理(icloud2.txt)的总和
    
    Args:
        vm_ip: 虚拟机IP地址
        temp_plist_path: 本地临时文件路径
    
    Returns:
        tuple: (total_count, unprocessed_count, processed_count)
    """
  #  logger.debug(f'[DEBUG] 开始计算总Apple ID数量 - VM IP: {vm_ip}')
    
    # 初始化计数
    unprocessed_count = 0
    processed_count = 0
    
    try:
        # 1. 获取未处理的Apple ID数量（icloud.txt）
        if os.path.exists(temp_plist_path):
            with open(temp_plist_path, 'r', encoding='utf-8') as f:
                apple_id_content = f.read()
            
            # 统计有效Apple ID数量
            unprocessed_count, _ = count_valid_apple_ids(apple_id_content)
        #    logger.debug(f'[DEBUG] 未处理Apple ID数量: {unprocessed_count}')
        else:
            logger.warning(f'[WARNING] 本地临时文件不存在: {temp_plist_path}')
        
        # 2. 同步并获取已处理的Apple ID数量（icloud2.txt）
        icloud2_local_path = sync_icloud2_file(vm_ip)
        if icloud2_local_path and os.path.exists(icloud2_local_path):
            with open(icloud2_local_path, 'r', encoding='utf-8') as f:
                icloud2_content = f.read()
            
            # 统计有效Apple ID数量
            processed_count, _ = count_valid_apple_ids(icloud2_content)
         #   logger.debug(f'[DEBUG] 已处理Apple ID数量: {processed_count}')
            
            # 清理临时文件
            os.remove(icloud2_local_path)
        else:
            logger.warning(f'[WARNING] 无法同步icloud2.txt文件或文件不存在')
        
        # 计算总数
        total_count = unprocessed_count + processed_count
        
        return total_count, unprocessed_count, processed_count
    except Exception as e:
        logger.error(f'[ERROR] 计算总Apple ID数量时发生异常: {str(e)}')
        # 出错时返回未处理数量作为总数
        return unprocessed_count, unprocessed_count, 0

# 辅助函数：写入日志
def write_log(process_id, message):
    process_log_dir = os.path.join(LOG_DIR, process_id)
    os.makedirs(process_log_dir, exist_ok=True)
    log_file = os.path.join(process_log_dir, f'{datetime.now().strftime("%Y%m%d")}.log')
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        # 确保message不包含多余的换行符，只在最后添加一个换行
        message_str = str(message).rstrip('\n')
        with open(log_file, 'a', encoding='utf-8') as f:
            log_entry = f'[{timestamp}] {message_str}\n'
            f.write(log_entry)
    except Exception as e:
        logger.error(f'[ERROR] 日志写入失败: {str(e)}')

# 辅助函数：通过SSH远程执行脚本
def run_ssh_remote_command(vm_ip, username, command):
    try:
        # 从config模块导入vm_password（如果存在）
        try:
            from config import vm_password
        except ImportError:
            vm_password = None
        
        # 使用SSHClient执行命令，传递密码参数
        with SSHClient(hostname=vm_ip, username=username, password=vm_password) as ssh_client:
            success, stdout, stderr, exit_code = ssh_client.execute_command(command, timeout=90)
            
        if success:
            return True, stdout.strip()
        else:
            logger.error(f'[ERROR] SSH命令执行失败 - 错误码: {exit_code}, 错误输出: {stderr.strip()}')
            return False, stderr.strip()
    except Exception as e:
        logger.error(f'[ERROR] SSH命令执行异常: {str(e)}')
        return False, str(e)

# 辅助函数：执行scpt脚本
def run_scpt_script(vm_ip, script_name, process_id=None):
    from config import appleid_login_timeout, icloud_wait_after_query
    url = f'http://{vm_ip}:{SCPTRUNNER_PORT}/run?path={SCRIPT_DIR}{script_name}'
    
    # 首先检查是否有停止标志，如果有则不执行脚本
    if process_id and stop_flags.get(process_id, False):
        logger.info(f'[INFO] 检测到进程停止标志，跳过执行脚本 - 进程ID: {process_id}, 脚本: {script_name}')
        return {'result': '进程已停止，跳过执行脚本'}
    
    # 检测scpt脚本进程前先检查停止标志
    if process_id and stop_flags.get(process_id, False):
        logger.info(f'[INFO] 检测到进程停止标志，跳过进程检测 - 进程ID: {process_id}, 脚本: {script_name}')
    else:
        vm_username = 'wx'  # 虚拟机用户名
        try:
            # 执行ps命令检查scpt相关进程
            ps_cmd = "ps aux | grep scpt | grep -v grep"
            
            # 循环等待，直到没有其他scpt脚本进程在运行
            max_wait_time = 300  # 最大等待时间（秒）
            wait_interval = 10  # 检查间隔（秒）
            start_wait_time = time.time()
            has_other_processes = True
            
            while has_other_processes:
                # 检查是否达到最大等待时间
                if time.time() - start_wait_time > max_wait_time:
                    logger.warning(f'[WARNING] 等待其他scpt脚本进程结束超时，继续执行')
                    break
                
                # 检查是否有停止标志
                if process_id and stop_flags.get(process_id, False):
                    logger.info(f'[INFO] 检测到进程停止标志，停止等待 - 进程ID: {process_id}')
                    break
                
                # 从config模块导入vm_password（如果存在）
                try:
                    from config import vm_password
                except ImportError:
                    vm_password = None
                    logger.debug(f'[DEBUG] 未找到vm_password配置，将尝试免密认证')
                
                # 使用SSHClient执行命令检查scpt进程
                with SSHClient(hostname=vm_ip, username=vm_username, password=vm_password, timeout=5) as ssh_client:
                    success, output, error, exit_code = ssh_client.execute_command(ps_cmd, timeout=10)
                
                # 分析输出，查找是否有scpt脚本进程在运行
                lines = []
                script_processes = []
                script_names = {}
                has_login_script = False
                has_logout_script = False
                
                if success and exit_code == 0:
                    lines = output.strip().split('\n')
                
                # 分析进程信息
                for line in lines:
                    if '/usr/bin/osascript' in line and '/macos_script/macos_scpt/macos11/' in line:
                        script_processes.append(line)
                        
                        # 提取脚本名称
                        for script_file in ['appleid_login.scpt', 'logout_icloud.scpt', 'queryiCloudAccount.scpt', 'login_restart.scpt']:
                            if script_file in line:
                                if script_file not in script_names:
                                    script_names[script_file] = 0
                                script_names[script_file] += 1
                                
                                # 检查是否同时存在登录和注销脚本
                                if script_file == 'appleid_login.scpt':
                                    has_login_script = True
                                elif script_file == 'logout_icloud.scpt':
                                    has_logout_script = True
                                break
                
                # 特殊处理：如果我们正在执行queryiCloudAccount.scpt，且只有appleid_login.scpt在运行，可以跳过等待
                is_executing_query = script_name == 'queryiCloudAccount.scpt'
                has_only_login_process = (len(script_processes) == 1 and 
                                         'appleid_login.scpt' in script_names and 
                                         script_names['appleid_login.scpt'] == 1 and
                                         not has_logout_script)
                
                # 检查是否有其他scpt脚本进程在运行（考虑特殊情况）
                if len(script_processes) > 0 and not (is_executing_query and has_only_login_process):
                    # 添加日志节流机制，避免短时间内重复打印相同的日志
                    current_time = time.time()
                    process_key = '\n'.join(script_processes)
                    
                    # 检查是否需要打印日志
                    if not hasattr(run_scpt_script, '_last_log_time') or not hasattr(run_scpt_script, '_last_process_key'):
                        run_scpt_script._last_log_time = 0
                        run_scpt_script._last_process_key = ''
                    
                    # 只有在以下情况打印日志：
                    # 1. 距离上次打印超过5秒
                    # 2. 或者进程列表发生了变化
                    if (current_time - run_scpt_script._last_log_time > 5) or (process_key != run_scpt_script._last_process_key):
                        run_scpt_script._last_log_time = current_time
                        run_scpt_script._last_process_key = process_key
                    
                    # 检测到多个正在运行的scpt脚本进程，执行restart_scptapp.scpt
                    if len(script_processes) > 1:
                        # 通过SSH执行restart_scptapp.scpt
                        try:
                            ssh_command = "osascript /Users/wx/Documents/macos_script/macos_scpt/macos11/restart_scptapp.scpt"
                            success, output = run_ssh_remote_command(vm_ip, "wx", ssh_command)
                            if success:
                                logger.info(f'[INFO] 成功执行restart_scptapp.scpt')
                                # 等待服务重启
                                time.sleep(5)
                            else:
                                logger.error(f'[ERROR] 执行restart_scptapp.scpt失败: {output}')
                        except Exception as e:
                            logger.error(f'[ERROR] 执行restart_scptapp.scpt时发生异常: {str(e)}')
                        
                        # 重置环境后，重新开始等待过程
                        has_other_processes = True
                        break  # 跳出当前循环，重新检查进程
                    
                    time.sleep(wait_interval)
                    has_other_processes = True
                else:
                    logger.info(f'[INFO] 没有检测到其他scpt脚本进程，可以执行脚本')
                    has_other_processes = False
                
                # 检查是否需要重置环境（即使没有其他进程，也可能需要处理异常情况）
                if not has_other_processes:
                    # 需要重置环境的条件：
                    # 1. 任何脚本有重复实例（相同名称的脚本运行多个）
                    # 2. appleid_login.scpt和logout_icloud.scpt同时存在
                    need_reset = False
                    reset_reason = ""
                    
                    # 检查是否有重复的脚本实例
                    for script, count in script_names.items():
                        if count > 1:
                            need_reset = True
                            reset_reason = f"检测到{script}脚本重复运行（{count}个实例）"
                            break
                    
                    # 检查是否同时存在登录和注销脚本
                    if not need_reset and has_login_script and has_logout_script:
                        need_reset = True
                        reset_reason = "检测到appleid_login.scpt和logout_icloud.scpt同时运行"
                    
                    # 如果需要重置环境，执行restart_scptapp.scpt
                    if need_reset:
                        # 执行前再次检查停止标志
                        if process_id and stop_flags.get(process_id, False):
                            logger.info(f'[INFO] 检测到进程停止标志，跳过环境重置 - 进程ID: {process_id}')
                            has_other_processes = False  # 不再等待
                        else:
                            logger.warning(f'[WARNING] {reset_reason}，执行restart_scptapp.scpt重置环境')
                            logger.debug(f'[DEBUG] 当前运行的脚本进程:\n' + '\n'.join(script_processes))
                            
                            # 通过SSH执行restart_scptapp.scpt
                            try:
                                ssh_command = "osascript /Users/wx/Documents/macos_script/macos_scpt/macos11/restart_scptapp.scpt"
                                success, output = run_ssh_remote_command(vm_ip, "wx", ssh_command)
                                if success:
                                    logger.info(f'[INFO] 成功执行restart_scptapp.scpt')
                                    # 等待服务重启
                                    time.sleep(icloud_wait_after_query)
                                else:
                                    logger.error(f'[ERROR] 执行restart_scptapp.scpt失败: {output}')
                                
                                # 重置环境后，需要重新开始等待过程，确保没有进程在运行
                                has_other_processes = True
                            except Exception as restart_e:
                                logger.error(f'[ERROR] 执行restart_scptapp.scpt时发生异常: {str(restart_e)}')
                                # 即使失败也要重新开始等待过程，允许继续执行appleid循环
                                has_other_processes = True
        except Exception as e:
            logger.error(f'[ERROR] 检测scpt脚本进程时发生异常: {str(e)}')
            # 继续执行，不阻止脚本运行
    
    # 为appleid_login.scpt设置单独的超时
    if script_name == 'appleid_login.scpt':
        timeout = appleid_login_timeout
        logger.info(f'[INFO] 使用特定超时设置: {timeout}秒 - 脚本: {script_name}')
    else:
        timeout = 90  # 其他脚本使用默认超时
    
    try:
        # 再次检查停止标志，确保在请求前检查
        if process_id and stop_flags.get(process_id, False):
            logger.info(f'[INFO] 检测到进程停止标志，跳过执行脚本 - 进程ID: {process_id}, 脚本: {script_name}')
            return {'result': '进程已停止，跳过执行脚本'}
        
        start_time = time.time()
        response = requests.get(url, timeout=timeout)
        elapsed_time = time.time() - start_time
       # logger.debug(f'[DEBUG] 脚本执行完成 - 响应状态码: {response.status_code}, 耗时: {elapsed_time:.2f}秒')
        response.raise_for_status()
        result = response.json()
        logger.debug(f'[DEBUG] 脚本执行结果: {json.dumps(result)}')
        return result
    except requests.exceptions.Timeout:
        logger.error(f'[ERROR] 脚本执行超时: {vm_ip} - {script_name}, 超时时间: {timeout}秒')
        
        # 如果是appleid_login.scpt超时，执行restart_scptapp.scpt然后重新尝试
        if script_name == 'appleid_login.scpt':
            logger.info(f'[INFO] appleid_login.scpt超时，执行restart_scptapp.scpt')
            # 通过SSH执行restart_scptapp.scpt
            try:
                ssh_command = "osascript /Users/wx/Documents/macos_script/macos_scpt/macos11/restart_scptapp.scpt"
                success, output = run_ssh_remote_command(vm_ip, "wx", ssh_command)
                if success:
                    logger.info(f'[INFO] 成功执行restart_scptapp.scpt')
                    # 等待服务重启
                    time.sleep(icloud_wait_after_query)
                    
                    # 检查是否有停止标志，如果有则不重新执行脚本
                    if process_id and stop_flags.get(process_id, False):
                        logger.info(f'[INFO] 检测到进程停止标志，跳过重新执行脚本 - 进程ID: {process_id}')
                        return {'result': '进程已停止，跳过重新执行脚本'}
                    
                    # 重新执行appleid_login.scpt
                    logger.info(f'[INFO] 重新执行appleid_login.scpt')
                    retry_response = requests.get(url, timeout=120)
                    retry_response.raise_for_status()
                    retry_result = retry_response.json()
                    logger.info(f'[INFO] 重新执行appleid_login.scpt成功: {json.dumps(retry_result)}')
                    return retry_result
                else:
                    logger.error(f'[ERROR] 执行restart_scptapp.scpt失败: {output}')
                    return {'result': f'appleid_login.scpt超时且重启失败: {output}'}
            except Exception as restart_e:
                logger.error(f'[ERROR] 执行restart_scptapp.scpt或重新执行appleid_login.scpt失败: {str(restart_e)}')
                return {'result': f'appleid_login.scpt超时且重启失败: {str(restart_e)}'}
        
        return {'result': '脚本执行超时'}
    except requests.exceptions.ConnectionError:
        error_message = f'[ERROR] 连接失败: {vm_ip}:{SCPTRUNNER_PORT}'
        logger.error(error_message)
        # 尝试通过SSH重启Scptrunner客户端（适用于所有虚拟机）
        # 检查是否有停止标志，如果有则不执行重启操作
        if process_id and stop_flags.get(process_id, False):
            logger.info(f'[INFO] 检测到进程停止标志，跳过SSH重启操作 - 进程ID: {process_id}')
        else:
            logger.debug(f'[DEBUG] 尝试通过SSH重启Scptrunner客户端 - VM IP: {vm_ip}')
            ssh_command = "osascript /Users/wx/Documents/macos_script/macos_scpt/macos11/restart_scptapp.scpt"
            success, output = run_ssh_remote_command(vm_ip, "wx", ssh_command)
            if success:
                #  logger.info(f'[INFO] Scptrunner客户端已通过SSH成功重启')
                # 重启后等待一段时间，然后尝试重新执行脚本
                time.sleep(10)
                
                # 再次检查是否有停止标志，如果有则不重新执行脚本
                if process_id and stop_flags.get(process_id, False):
                    logger.info(f'[INFO] 检测到进程停止标志，跳过重新执行脚本 - 进程ID: {process_id}')
                    return {'result': '进程已停止，跳过重新执行脚本'}
                
                logger.debug(f'[DEBUG] 尝试重新执行脚本 - VM IP: {vm_ip}, 脚本名称: {script_name}')
                try:
                    response = requests.get(url, timeout=300)
                    response.raise_for_status()
                    result = response.json()
                    logger.debug(f'[DEBUG] 重新执行脚本成功: {json.dumps(result)}')
                    return result
                except Exception as retry_e:
                  #  logger.error(f'[ERROR] 重新执行脚本失败: {str(retry_e)}')
                    return {'result': f'连接失败，已尝试重启但仍失败: {str(retry_e)}'}
            else:
                logger.error(f'[ERROR] SSH重启Scptrunner客户端失败: {output}')
                
        return {'result': f'连接失败: {vm_ip}:{SCPTRUNNER_PORT}'}
    except Exception as e:
        logger.error(f'[ERROR] 脚本执行异常: {str(e)}')
        return {'result': f'脚本执行失败: {str(e)}'}

# 辅助函数：从远程下载文件
def download_file_from_remote(vm_ip, remote_path, local_path):
    #logger.debug(f'[DEBUG] 准备同步远程appleid文本文件 - VM IP: {vm_ip}, 远程路径: {remote_path}, 本地路径: {local_path}')
    try:
        # 使用SSHClient从远程下载文件
        with SSHClient(hostname=vm_ip, username='wx') as ssh_client:
            start_time = time.time()
            success = ssh_client.download_file(remote_path, local_path)
            elapsed_time = time.time() - start_time
           # logger.debug(f'[DEBUG] 下载文件完成，状态: {success}, 耗时: {elapsed_time:.2f}秒')
        
        if success:
          #  logger.info(f'[INFO] 成功从远程下载文件到: {local_path}')
            return True
        else:
          #  logger.error(f'[ERROR] 从远程下载文件失败')
            return False
    except Exception as e:
       # logger.error(f'[ERROR] 从远程下载文件时发生异常: {str(e)}')
        return False

# 辅助函数：传输appleid文本文件
def transfer_appleid_file(vm_ip, apple_id_text):
    """传输未处理的Apple ID文本到虚拟机
    
    Args:
        vm_ip: 虚拟机IP地址
        apple_id_text: 未处理的Apple ID文本内容
    
    Returns:
        bool: 传输是否成功
    """
    logger.debug(f'[DEBUG] 准备传输未处理的Apple ID文件 - VM IP: {vm_ip}, 目标路径: {ICLOUD_TXT_PATH}')
    temp_file = None
    success = False  # 初始化success变量
    try:
        # 创建临时文件
        temp_file = os.path.join(os.environ.get('TEMP', '/tmp'), 'icloud.txt')
      #  logger.debug(f'[DEBUG] 创建临时文件: {temp_file}')
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(apple_id_text)
       # logger.debug(f'[DEBUG] 临时文件创建成功，内容长度: {len(apple_id_text)} 字符')
        
        # 使用SSHClient传输文件
        try:
            with SSHClient(hostname=vm_ip, username='wx') as ssh_client:
                start_time = time.time()
                success, upload_msg = ssh_client.upload_file(temp_file, ICLOUD_TXT_PATH)
                elapsed_time = time.time() - start_time
              #  logger.debug(f'[DEBUG] 文件上传完成，状态: {success}, 消息: {upload_msg}, 耗时: {elapsed_time:.2f}秒')
                
                # 验证文件是否成功上传
                if success:
                    file_exists = ssh_client.check_file_exists(ICLOUD_TXT_PATH)
                    if not file_exists:
                        logger.error(f'[ERROR] 验证失败：文件未在远程路径找到')
                        success = False
        except Exception as e:
           # logger.error(f'[ERROR] SSH连接失败: {str(e)}')
            return False
        
        # 删除临时文件
        if os.path.exists(temp_file):
            os.remove(temp_file)
          #  logger.debug(f'[DEBUG] 临时文件已删除: {temp_file}')
        
        if success:
         #   logger.info(f'[INFO] 未处理的Apple ID文件传输成功到虚拟机')
            return success
    except Exception as e:
      #  logger.error(f'[ERROR] 传输Apple ID文件时发生异常: {str(e)}')
        # 清理临时文件
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
          #  logger.debug(f'[DEBUG] 异常情况下临时文件已删除: {temp_file}')
    return False

# 辅助函数：同步icloud2.txt文件（已处理的Apple ID）
def sync_icloud2_file(vm_ip, local_path=None):
    """从虚拟机同步icloud2.txt文件到本地
    
    Args:
        vm_ip: 虚拟机IP地址
        local_path: 本地保存路径，如果为None则使用临时目录
    
    Returns:
        str: 本地文件路径，如果同步失败返回None
    """
  #  logger.debug(f'[DEBUG] 准备同步icloud2.txt文件 - VM IP: {vm_ip}, 源路径: {ICLOUD2_TXT_PATH}')
    
    if not local_path:
        local_path = os.path.join(os.environ.get('TEMP', '/tmp'), 'icloud2.txt')
    
    try:
        with SSHClient(hostname=vm_ip, username='wx') as ssh_client:
            # 检查远程文件是否存在
            success, stdout, stderr, exit_code = ssh_client.execute_command(f'test -f "{ICLOUD2_TXT_PATH}" && echo "exists" || echo "not_exists"')
            file_exists = stdout if success else "not_exists"
            if file_exists.strip() != 'exists':
               # logger.warning(f'[WARNING] 远程icloud2.txt文件不存在: {ICLOUD2_TXT_PATH}')
                return None
            
            start_time = time.time()
            success = ssh_client.download_file(ICLOUD2_TXT_PATH, local_path)
            elapsed_time = time.time() - start_time
           # logger.debug(f'[DEBUG] icloud2.txt下载完成，状态: {success}, 耗时: {elapsed_time:.2f}秒, 本地路径: {local_path}')
            
            return local_path if success else None
    except Exception as e:
       # logger.error(f'[ERROR] 同步icloud2.txt文件时发生异常: {str(e)}')
        return None

# 辅助函数：等待虚拟机启动完成

def wait_for_vm_ready(vm_ip, timeout=300):
    logger.info(f'[INFO] 开始等待虚拟机启动 - IP: {vm_ip}, 超时时间: {timeout}秒')
    
    # 定义虚拟机用户名
    vm_username = 'wx'  # 虚拟机用户名
    
    # 导入必要的模块
    import os
    from config import temp_dir
    
    start_time = time.time()
    attempt = 0
    
    # 检查是否是五码更换后的重启
    is_wuma_restart = False
    process_id = None
    
    # 查找对应的进程ID
    for process in processes:
        if process.get('client') == vm_ip:
            process_id = process.get('id')
            break
    
    # 检查五码重启标志
    if process_id:
        wuma_restart_flag_file = os.path.join(temp_dir, f'wuma_restart_{process_id}.flag')
        if os.path.exists(wuma_restart_flag_file):
            is_wuma_restart = True
            logger.info(f"[INFO] 检测到五码更换后的重启 - 进程ID: {process_id}")
            # 删除标志文件
            try:
                os.remove(wuma_restart_flag_file)
                logger.debug(f"[DEBUG] 已删除五码重启标志文件")
            except Exception as e:
                logger.warning(f"[WARNING] 删除五码重启标志文件失败: {str(e)}")
    

    while time.time() - start_time < timeout:
        attempt += 1
        elapsed = time.time() - start_time
        
        # 打印每次尝试的详细日志，便于调试
        logger.info(f'[INFO] 检查虚拟机状态 (尝试 {attempt}) - 已等待: {elapsed:.1f}秒')
        
        try:
            # 检查IP是否存活
            #logger.debug(f'[DEBUG] 正在检查虚拟机连通性 - IP: {vm_ip}')
            # 使用socket检查IP是否可达
            ping_success = False
            try:
                # 尝试连接到SSH端口
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    if s.connect_ex((vm_ip, 22)) == 0:
                        ping_success = True
                # 如果SSH端口不可达，尝试UDP
                if not ping_success:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                        s.settimeout(2)
                        try:
                            s.sendto(b'ping', (vm_ip, 80))
                            ping_success = True
                        except:
                            ping_success = False
            except Exception as e:
               # logger.warning(f'[WARNING] 连接检查异常: {str(e)}')
                ping_success = False
            
            if not ping_success:
               # logger.warning(f'[WARNING] 虚拟机IP连接失败 - IP: {vm_ip}')
                time.sleep(10)  # 10秒间隔重试
                continue
            
           # logger.info(f'[INFO] 虚拟机IP连接成功 - IP: {vm_ip}')
            
            # 检查8787端口（进程端口）是否开放 - 使用socket
           # logger.debug(f'[DEBUG] 检查8787端口 - IP: {vm_ip}')
            port_open = False
            
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    if s.connect_ex((vm_ip, 8787)) == 0:
                        port_open = True
                        logger.info(f'[INFO] 8787端口开放')
            except Exception as port_error:
                logger.warning(f'[WARNING] 端口检查失败: {str(port_error)}')
            
            if port_open:
              #  logger.info(f'[INFO] 8787端口检查成功 - IP: {vm_ip}')
                # 端口已开放，检查SSH连接
               # logger.debug(f'[DEBUG] 检查SSH连接 - IP: {vm_ip}')
                
                try:
                    # 使用SSHClient检查SSH连接
                    # 从config模块导入vm_password（如果存在）
                    try:
                        from config import vm_password
                    except ImportError:
                        vm_password = None
                        logger.debug(f'[DEBUG] 未找到vm_password配置，将尝试免密认证')
                    
                    with SSHClient(hostname=vm_ip, username=vm_username, password=vm_password, timeout=5) as ssh_client:
                        success, output, error, exit_code = ssh_client.execute_command("echo connected", timeout=8)
                        if success:
                         #   logger.info(f'[INFO] 虚拟机已完全就绪 - IP: {vm_ip}, 所有检查均通过')
                            return True
                        else:
                            logger.warning(f'[WARNING] SSH命令执行失败 - 退出码: {exit_code}, 输出: {error}')
                except Exception as ssh_error:
                    logger.error(f'[ERROR] SSH连接失败: {str(ssh_error)}')
            else:
                logger.warning(f'[WARNING] 8787端口未开放 - IP: {vm_ip}')
                
                # 检查是否是五码更换后的重启，如果是则跳过stop_scptapp.scpt调用
                if is_wuma_restart:
                    logger.info(f'[INFO] 五码更换后的重启，跳过stop_scptapp.scpt调用 - IP: {vm_ip}')
                else:
                    # 尝试通过SSH调用restart_scptapp.scpt启动远端app客户端
                    try:
                        logger.info(f'[INFO] 尝试通过SSH启动远端app客户端 - IP: {vm_ip}')
                        # 导入配置获取脚本目录
                        from config import macos_script_dir, restart_scptRunner
                        
                        # 获取脚本文件名（仅文件名部分）
                        script_filename = 'restart_scptapp.scpt'
                        
                        # 构建本地脚本完整路径
                        local_script_path = os.path.join(macos_script_dir, script_filename)
                        logger.debug(f'[DEBUG] 本地脚本路径: {local_script_path}')
                        
                        # 在虚拟机上的脚本路径，使用config.py中的restart_scptRunner配置
                        vm_script_path = f'{restart_scptRunner}{script_filename}'
                     #   logger.debug(f'[DEBUG] 虚拟机脚本路径: {vm_script_path}')
                        
                        # 从config模块导入vm_password（如果存在）
                        try:
                            from config import vm_password
                        except ImportError:
                            vm_password = None
                            logger.debug(f'[DEBUG] 未找到vm_password配置，将尝试免密认证')
                        
                        with SSHClient(hostname=vm_ip, username=vm_username, password=vm_password, timeout=5) as ssh_client:
                            # 首先检查虚拟机上是否存在脚本文件
                            check_cmd = f'test -f {vm_script_path} && echo "exists" || echo "not exists"'
                            success_check, output_check, _, _ = ssh_client.execute_command(check_cmd, timeout=10)
                            
                            # 在执行restart_scptapp.scpt之前，先检查是否有scpt进程在运行
                            ps_cmd = "ps aux | grep scpt | grep -v grep"
                            check_success, check_output, _, _ = ssh_client.execute_command(ps_cmd, timeout=10)
                            if check_success and not check_output.strip():
                                logger.warning(f'[WARNING] 未检测到scpt进程运行，跳过执行restart_scptapp.scpt')
                                success = False  # 避免执行restart_scptapp.scpt
                            elif success_check and "exists" in output_check:
                                # 脚本文件存在，直接执行
                                cmd = f'osascript {vm_script_path}'
                                success, output, error, exit_code = ssh_client.execute_command(cmd, timeout=30)
                                
                                if success and exit_code == 0:
                                    logger.info(f'[INFO] 成功调用restart_scptapp.scpt启动远端app客户端 - IP: {vm_ip}')
                                    # 给服务一些时间启动
                                    time.sleep(10)
                                else:
                                    logger.warning(f'[WARNING] 调用restart_scptapp.scpt失败 - 退出码: {exit_code}, 错误: {error}')
                            else:
                                # 如果脚本不存在，尝试从本地上传
                                if os.path.exists(local_script_path):
                                    logger.info(f'[INFO] 尝试上传脚本到虚拟机 - {vm_script_path}')
                                    upload_success = ssh_client.upload_file(local_script_path, vm_script_path)
                                    if upload_success:
                                        logger.info(f'[INFO] 脚本上传成功，尝试执行')
                                        # 上传成功后执行脚本
                                        cmd = f'osascript {vm_script_path}'
                                        success, output, error, exit_code = ssh_client.execute_command(cmd, timeout=30)
                                        
                                        if success and exit_code == 0:
                                            logger.info(f'[INFO] 成功调用restart_scptapp.scpt启动远端app客户端 - IP: {vm_ip}')
                                            time.sleep(10)
                                        else:
                                            logger.warning(f'[WARNING] 调用上传的restart_scptapp.scpt失败 - 退出码: {exit_code}, 错误: {error}')
                                    else:
                                        logger.error(f'[ERROR] 脚本上传失败 - 无法复制到虚拟机')
                                else:
                                    logger.error(f'[ERROR] 本地脚本文件不存在: {local_script_path}')
                    except Exception as ssh_error:
                            logger.error(f'[ERROR] SSH调用restart_scptapp.scpt时出错: {str(ssh_error)}')
                            import traceback
                            logger.debug(f'[DEBUG] 异常堆栈: {traceback.format_exc()}')
                
                # 8787端口未开放，但IP已可达，可能服务尚未启动，尝试等待更长时间
                time.sleep(15)  # 稍微延长等待时间
                continue
                
        except Exception as e:
            logger.error(f'[ERROR] 检查虚拟机状态异常: {str(e)}')
            import traceback
            logger.debug(f'[DEBUG] 异常堆栈: {traceback.format_exc()}')
        
        time.sleep(10)  # 保持10秒的检查间隔
    
    logger.warning(f'[WARNING] 虚拟机启动超时 - IP: {vm_ip}, 等待时间: {timeout}秒')
    return False

# 虚拟机重启后自动监控并重启进程的函数
def monitor_and_restart_process_after_reboot(vm_ip, process_id, transfer_icloud_file=True):
    """
    监控虚拟机重启后的状态，并在条件满足时重新启动进程
    
    Args:
        vm_ip: 虚拟机IP地址
        process_id: 需要重启的进程ID
        transfer_icloud_file: 是否需要传输icloud.txt文件（仅在创建进程时为True）
    
    Returns:
        bool: 进程重启是否成功
    """
    # 导入必要的模块
    import os
  #  logger.info(f'[INFO] 开始监控虚拟机重启后状态 - IP: {vm_ip}, 进程ID: {process_id}')
    
    # 查找进程信息
    process = None
    for p in processes:
        if p['id'] == process_id:
            process = p
            break
    
    if not process:
      #  logger.error(f'[ERROR] 找不到指定进程 - 进程ID: {process_id}')
        return False
    
    # 等待虚拟机完全就绪（这会尝试执行restart_scptapp.scpt脚本）
    vm_ready = wait_for_vm_ready(vm_ip)
    if not vm_ready:
     #   logger.error(f'[ERROR] 虚拟机启动超时，无法重启进程 - IP: {vm_ip}, 进程ID: {process_id}')
        return False
    
   # logger.info(f'[INFO] 虚拟机已就绪，准备重启进程 - 进程ID: {process_id}')
    
    # 虚拟机已就绪且restart_scptapp.scpt脚本执行成功，立即更新状态为执行中
    process['status'] = '执行中'
    update_process_status(process_id, '执行中')
    logger.info(f'[INFO] 更新进程状态为执行中 - 进程ID: {process_id}')
    write_log(process_id, f'进程重启执行: {process["name"]}')
    
    # 进程重启前，同步远程的三个文件到本地logs进程目录appleid目录
    logger.info(f'[INFO] 进程重启前，同步远程的三个文件: icloud.txt, icloud2.txt, error.txt')
    write_log(process_id, '进程重启前，同步远程文件: icloud.txt, icloud2.txt, error.txt')
    
    # 同步文件函数
    def sync_remote_files_to_local():
        """同步远端的三个文件到本地logs进程目录appleid目录"""
        appleid_log_dir = os.path.join(LOG_DIR, process_id, 'appleid')
        os.makedirs(appleid_log_dir, exist_ok=True)
        
        local_files = {
            'icloud.txt': os.path.join(appleid_log_dir, 'icloud.txt'),
            'icloud2.txt': os.path.join(appleid_log_dir, 'icloud2.txt'),
            'error.txt': os.path.join(appleid_log_dir, 'error.txt')
        }
        remote_files = {
            'icloud.txt': ICLOUD_TXT_PATH,
            'icloud2.txt': ICLOUD2_TXT_PATH,
            'error.txt': ERROR_TXT_PATH
        }
        
        sync_results = {}
        for file_name, remote_path in remote_files.items():
            try:
                local_path = local_files[file_name]
                if download_file_from_remote(vm_ip, remote_path, local_path):
                    logger.info(f'[INFO] 成功同步文件: {file_name} 到 {local_path}')
                    sync_results[file_name] = 'success'
                else:
                    logger.warning(f'[WARNING] 同步文件: {file_name} 失败')
                    sync_results[file_name] = 'failed'
            except Exception as e:
                logger.error(f'[ERROR] 同步文件 {file_name} 时发生异常: {str(e)}')
                sync_results[file_name] = f'error: {str(e)}'
        
        return sync_results
    
    # 执行文件同步
    try:
        sync_results = sync_remote_files_to_local()
        write_log(process_id, f'文件同步结果: {json.dumps(sync_results)}')
    except Exception as sync_error:
        logger.error(f'[ERROR] 同步文件时发生异常: {str(sync_error)}')
        write_log(process_id, f'文件同步异常: {str(sync_error)}')
    
    # 如果需要传输icloud.txt文件（仅在创建进程时）
    if transfer_icloud_file:
      #  logger.info(f'[INFO] 准备传输icloud.txt文件 - 进程ID: {process_id}')
        try:
            from config import appleid_unused_dir
            
            # 获取并传输Apple ID文件
            apple_id_filename = process['apple_id']
            apple_id_file_path = os.path.join(appleid_unused_dir, apple_id_filename)
            
            # 检查文件是否存在
            if not os.path.exists(apple_id_file_path):
            #    logger.error(f'[ERROR] Apple ID文件不存在: {apple_id_file_path}')
                return False
            
            # 读取文件内容
            with open(apple_id_file_path, 'r', encoding='utf-8') as f:
                apple_id_content = f.read()
            
            # 传输文件
            transfer_success = transfer_appleid_file(vm_ip, apple_id_content)
            if not transfer_success:
           #     logger.error(f'[ERROR] icloud.txt文件传输失败 - 进程ID: {process_id}')
                return False
            
           # logger.info(f'[INFO] icloud.txt文件传输成功 - 进程ID: {process_id}')
        except Exception as e:
           # logger.error(f'[ERROR] 传输icloud.txt文件时发生异常: {str(e)}')
            return False
    else:
       # logger.info(f'[INFO] 重新启动进程时，从远程下载icloud.txt到本地临时文件 - 进程ID: {process_id}')
        try:
            # 从远程下载icloud.txt到本地临时文件
            download_success = download_file_from_remote(vm_ip, ICLOUD_TXT_PATH, TEMP_PLIST_PATH)
            if download_success:
             #   logger.info(f'[INFO] 从远程下载icloud.txt到本地临时文件成功 - 进程ID: {process_id}')
                # 检查下载的icloud.txt是否为空
                with open(TEMP_PLIST_PATH, 'r', encoding='utf-8') as f:
                    apple_id_content = f.read()
                
                if not apple_id_content.strip():
                   # logger.info(f'[INFO] 远程icloud.txt为空，直接标记进程为已完成')
                    process['status'] = '已完成'
                    update_process_status(process_id, '已完成')
                    return True
                
                # 统计远程文件中的有效Apple ID数量
                apple_ids = apple_id_content.strip().split('\n')
                non_empty_apple_ids = [id.strip() for id in apple_ids if id.strip()]
              #  logger.info(f'[INFO] 远程icloud.txt中发现 {len(non_empty_apple_ids)} 个有效Apple ID')
                
                # 同步icloud2.txt文件以获取已处理的Apple ID数量
             #   logger.info(f'[INFO] 重新启动时同步icloud2.txt文件 - 进程ID: {process_id}')
                icloud2_local_path = sync_icloud2_file(vm_ip)
                if icloud2_local_path and os.path.exists(icloud2_local_path):
                    with open(icloud2_local_path, 'r', encoding='utf-8') as f:
                        icloud2_content = f.read()
                    # 统计已处理的Apple ID数量
                    processed_count, _ = count_valid_apple_ids(icloud2_content)
                    total_count = len(non_empty_apple_ids) + processed_count
                  #  logger.info(f'[INFO] 重启时同步完成 - 总数: {total_count}, 未处理: {len(non_empty_apple_ids)}, 已处理: {processed_count}')
                    # 更新进程信息
                    process['total_count'] = total_count
                    process['processed_count'] = processed_count
                    process['progress'] = int((processed_count / total_count) * 100) if total_count > 0 else 0
                    # 清理临时文件
                    os.remove(icloud2_local_path)
                else:
                    logger.warning(f'[WARNING] 重启时无法同步icloud2.txt文件')
            else:
               # logger.warning(f'[WARNING] 从远程下载icloud.txt失败，尝试使用本地原始Apple ID文件')
                # 尝试使用本地原始Apple ID文件
                from config import appleid_unused_dir
                
                apple_id_filename = process['apple_id']
                apple_id_file_path = os.path.join(appleid_unused_dir, apple_id_filename)
                
                if os.path.exists(apple_id_file_path):
                    logger.info(f'[INFO] 读取本地Apple ID文件: {apple_id_file_path}')
                    # 读取文件内容
                    with open(apple_id_file_path, 'r', encoding='utf-8') as f:
                        apple_id_content = f.read()
                    # 保存到临时文件
                    with open(TEMP_PLIST_PATH, 'w', encoding='utf-8') as f:
                        f.write(apple_id_content)
                 #   logger.info(f'[INFO] 已将本地Apple ID文件内容保存到临时文件: {TEMP_PLIST_PATH}')
                else:
                    logger.error(f'[ERROR] 本地Apple ID文件也不存在: {apple_id_file_path}')
        except Exception as e:
            logger.error(f'[ERROR] 从远程下载icloud.txt失败: {str(e)}')
            # 即使下载失败，我们仍然尝试启动进程，因为可能有之前的临时文件可用
    
    # 继续启动进程（直接执行，不创建新线程，因为已经在独立线程中运行）
    try:
        # 直接调用execute_process函数，不需要再创建新线程
        execute_process(process_id, transfer_icloud_file)
        
        logger.info(f'[INFO] 进程已在独立线程中启动 - 进程ID: {process_id}')
        return True
    except Exception as e:
        logger.error(f'[ERROR] 启动进程时发生异常: {str(e)}')
        process['status'] = '失败'
        update_process_status(process_id, '失败')
        write_log(process_id, f'进程启动失败: {str(e)}')
        return False

# 辅助函数：执行五码更换
def change_wuma(vm_ip, wuma_config):
    logger.debug(f'[DEBUG] 准备更换五码 - VM IP: {vm_ip}, 配置: {wuma_config}')
    try:
        # 导入必要的模块和配置
        from config import wuma_config_dir, plist_template_dir, plist_chengpin_template_dir, oc_config_path, boot_config_path
        import os, uuid, base64, time
        
        # 查找对应的虚拟机名称和进程ID
        vm_name = None
        process_id = None
        for process in processes:
            if process.get('client') == vm_ip:
                vm_name = process.get('name')
                process_id = process.get('id')
                break
        
        if not vm_name:
            # 如果找不到虚拟机名称，使用IP作为名称
            vm_name = f'VM_{vm_ip}'
            logger.warning(f'[WARNING] 未找到虚拟机名称，使用临时名称: {vm_name}')
        
        logger.info(f'[INFO] 使用虚拟机名称: {vm_name} 进行五码更换')
        
        # 构建配置文件路径
        if not wuma_config.endswith('.txt'):
            wuma_config = f'{wuma_config}.txt'
        config_file_path = os.path.join(wuma_config_dir, wuma_config)
        
        # 检查配置文件是否存在
        if not os.path.exists(config_file_path):
            logger.error(f'[ERROR] 五码配置文件不存在: {config_file_path}')
            return False
        
        # 使用文件锁确保五码分配的原子性
        lock_file_path = config_file_path + '.lock'
        logger.debug(f"[DEBUG] 尝试获取五码配置文件锁: {lock_file_path}")
        
        # 导入文件锁相关模块
        if os.name == 'nt':
            import msvcrt
        else:
            import fcntl
        
        with open(lock_file_path, 'w') as lock_file:
            # 获取文件锁，最多等待30秒
            max_wait_time = 30
            start_time = time.time()
            while True:
                try:
                    if os.name == 'nt' and msvcrt:  # Windows系统
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    elif 'fcntl' in locals() and fcntl:  # Unix/Linux系统
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    else:
                        # 如果没有可用的文件锁机制，使用简单的文件存在检查
                        if os.path.exists(lock_file_path + '.busy'):
                            raise IOError("Lock file exists")
                        with open(lock_file_path + '.busy', 'w') as busy_file:
                            busy_file.write(str(os.getpid()))
                    logger.debug("[DEBUG] 成功获取五码配置文件锁")
                    break
                except (IOError, OSError):
                    if time.time() - start_time > max_wait_time:
                        logger.error("[ERROR] 获取五码配置文件锁超时")
                        return False
                    time.sleep(0.1)
            
            # 在锁保护下读取和分配五码
            with open(config_file_path, 'r', encoding='utf-8') as f:
                wuma_lines = f.readlines()
            
            # 过滤有效行
            def is_valid_wuma_file_line(line):
                return len(line.split(':')) >= 7
            
            valid_wuma_lines = [line.strip() for line in wuma_lines if line.strip() and is_valid_wuma_file_line(line.strip())]
            
            if not valid_wuma_lines:
                logger.error("[ERROR] 配置文件中没有有效的五码数据")
                return False
            
            # 为当前虚拟机分配一个五码
            allocated_wuma_line = valid_wuma_lines[0]
            remaining_wuma_lines = valid_wuma_lines[1:]
            
            # 立即更新配置文件，移除已分配的五码
            with open(config_file_path, 'w', encoding='utf-8') as f:
                for line in remaining_wuma_lines:
                    f.write(line + '\n')
            
            logger.info(f"[INFO] 已分配1个五码，剩余{len(remaining_wuma_lines)}个")
            
            # 释放文件锁
            try:
                if os.name == 'nt' and msvcrt:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                elif 'fcntl' in locals() and fcntl:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                else:
                    # 删除简单锁文件
                    busy_lock_path = lock_file_path + '.busy'
                    if os.path.exists(busy_lock_path):
                        os.remove(busy_lock_path)
            except Exception as lock_error:
                logger.warning(f"[WARNING] 释放文件锁时出错: {lock_error}")
        
        # 检测虚拟机的macOS版本
        def detect_macos_version(vm_name_str):
            vm_name_lower = vm_name_str.lower()
            if any(version in vm_name_lower for version in ['macos10.15', 'macos11','macos12','macos13','macos14', 'macos15']):
                return 'macos10.15+'
            elif any(version in vm_name_lower for version in ['macos10.12', 'macos10.13', 'macos10.14']):
                return 'legacy'
            else:
                return 'legacy'
        
        macos_version = detect_macos_version(vm_name)
        
        # 根据版本选择模板文件
        if macos_version == 'macos10.15+':
            template_filename = 'opencore.plist'
            logger.info(f"[INFO] 检测到macos10.15+版本，使用OpenCore模板")
        else:
           template_filename = 'opencore.plist'
           logger.info(f"[INFO] 检测到macos10.15+版本，使用OpenCore模板")
        
        plist_template_path = os.path.join(plist_template_dir, template_filename)
        logger.info(f"[INFO] 检查plist模板文件: {plist_template_path}")
        
        if not os.path.exists(plist_template_path):
            logger.error(f"[ERROR] plist模板文件不存在: {plist_template_path}")
            return False
        
        with open(plist_template_path, 'r', encoding='utf-8') as f:
            plist_template = f.read()
        
        # 解析五码数据
        wuma_parts = allocated_wuma_line.split(':')
        if len(wuma_parts) != 7:
            logger.error(f"[ERROR] 五码格式错误: {allocated_wuma_line}")
            return False
        
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
            if not all(c in '0123456789ABCDEFabcdef' for c in rom):
                logger.warning(f"[WARNING] ROM值 {rom} 包含非十六进制字符，使用UTF-8编码")
                rom_bytes = rom.encode('utf-8')
            else:
                rom_pairs = [rom[i:i + 2] for i in range(0, len(rom), 2)]
                rom_bytes = bytes([int(pair, 16) for pair in rom_pairs])
            
            rom_base64 = base64.b64encode(rom_bytes).decode('utf-8')
            rom_formatted = rom_base64
        except ValueError as e:
            logger.error(f"[ERROR] ROM转换失败: {e}, 使用UTF-8编码")
            rom_bytes = rom.encode('utf-8')
            rom_base64 = base64.b64encode(rom_bytes).decode('utf-8')
            rom_formatted = rom_base64
        
        # 替换plist模板中的占位符
        plist_content = plist_template
        plist_content = plist_content.replace('$1', model)
        plist_content = plist_content.replace('$3', serial_number)
        plist_content = plist_content.replace('$5', rom_formatted)
        plist_content = plist_content.replace('$6', mlb)
        plist_content = plist_content.replace('$7', sm_uuid)
        
        # 对于legacy版本，需要替换$2和$4占位符
        if macos_version == 'legacy':
            plist_content = plist_content.replace('$2', board_id)
            plist_content = plist_content.replace('$4', custom_uuid)
        
        # 生成plist文件
        plist_filename = f"{vm_name}.plist"
        plist_file_path = os.path.join(plist_chengpin_template_dir, plist_filename)
        os.makedirs(os.path.dirname(plist_file_path), exist_ok=True)
        
        with open(plist_file_path, 'w', encoding='utf-8') as f:
            f.write(plist_content)
        
        logger.info(f"[INFO] 生成plist文件: {plist_file_path}")
        
        # 验证文件是否成功创建
        if not os.path.exists(plist_file_path):
            logger.error(f"[ERROR] plist文件创建失败，文件不存在: {plist_file_path}")
            return False
        else:
            logger.debug(f"[DEBUG] plist文件创建成功，大小: {os.path.getsize(plist_file_path)} 字节")
        
        # 根据版本设置不同的上传路径
        if macos_version == 'macos10.15+':
            remote_config_path = oc_config_path
        else:
            remote_config_path = oc_config_path
        
        # 执行mount_efi.sh脚本
        from config import sh_script_remote_path, vm_username
        script_path = f"{sh_script_remote_path}/mount_efi.sh"
        logger.info(f"[INFO] 执行mount脚本: {script_path}")
        
        # 执行远程脚本
        script_success = False
        output = ""
        script_executed = False
        try:
            # 使用现有的run_ssh_remote_command函数执行远程脚本
            script_success, output = run_ssh_remote_command(vm_ip, vm_username, script_path)
            script_executed = True
            if script_success:
                logger.info(f"[INFO] mount_efi.sh执行成功")
            else:
                logger.warning(f"[WARNING] mount_efi.sh执行失败: {output}")
        except Exception as script_error:
            logger.error(f"[ERROR] 执行mount_efi.sh时发生异常: {str(script_error)}")
            script_success = False
            output = str(script_error)
        
        logger.info(f"[INFO] mount_efi.sh脚本执行状态: {'已执行' if script_executed else '未执行'}, {'成功' if script_success else '失败'}")
        
        # 传输plist文件到虚拟机 - 使用scp命令
        transfer_success = False
        transfer_message = ""
        
        try:
            # 验证本地文件是否存在
            if not os.path.exists(plist_file_path):
                logger.error(f"[ERROR] 本地plist文件不存在: {plist_file_path}")
                transfer_message = f"本地文件不存在: {plist_file_path}"
                return False
            
            # 使用SSHClient传输文件
            logger.info(f"[INFO] 使用SSHClient传输文件: {plist_file_path} -> {vm_username}@{vm_ip}:{remote_config_path}")
            
            # 使用SSHClient传输文件
            try:
                with SSHClient(hostname=vm_ip, username=vm_username) as ssh_client:
                    start_time = time.time()
                    transfer_success = ssh_client.upload_file(plist_file_path, remote_config_path)
                    elapsed_time = time.time() - start_time
                
                if transfer_success:
                    transfer_message = f"文件传输成功，耗时: {elapsed_time:.2f}秒"
                    logger.info(f"[INFO] {transfer_message}")
                else:
                    transfer_message = "文件传输失败"
                    logger.error(f"[ERROR] {transfer_message}")
                
            except Exception as scp_error:
                logger.error(f"[ERROR] 执行文件传输时发生异常: {str(scp_error)}")
                transfer_message = str(scp_error)
                transfer_success = False
        except Exception as e:
            logger.error(f"[ERROR] 执行文件传输时发生异常: {str(e)}")
            transfer_message = str(e)
            transfer_success = False
        # 如果scp传输失败，尝试使用密码方式（如果有密码）
        if not transfer_success:
            try:
                from config import vm_password
                if vm_password:
                    logger.info("[INFO] scp传输失败，尝试使用密码方式传输")
                    
                    # 使用SSHClient和密码方式传输文件（适用于所有平台）
                    try:
                        with SSHClient(hostname=vm_ip, username=vm_username, password=vm_password) as ssh_client:
                            transfer_success = ssh_client.upload_file(plist_file_path, remote_config_path)
                            
                        if transfer_success:
                            transfer_message = "使用密码方式SSH传输成功"
                            logger.info(f"[INFO] {transfer_message}")
                        else:
                            transfer_message = "使用密码方式SSH传输失败"
                            logger.error(f"[ERROR] {transfer_message}")
                    except Exception as e:
                        logger.error(f"[ERROR] 使用密码方式传输时发生异常: {str(e)}")
            except ImportError:
                logger.warning("[WARNING] 无法导入vm_password配置")
            except Exception as pass_error:
                logger.error(f"[ERROR] 使用密码方式传输时发生异常: {str(pass_error)}")
        
        # 检查传输是否成功
        if not transfer_success:
            logger.error(f"[ERROR] 文件传输失败: {transfer_message}")
            return False
        else:
            logger.info(f"[INFO] 文件传输成功: {transfer_message}")
        
        # 备份已使用的五码
        backup_dir = os.path.join(wuma_config_dir, 'install')
        os.makedirs(backup_dir, exist_ok=True)
        config_filename = os.path.basename(config_file_path)
        config_filename = os.path.splitext(config_filename)[0]
        backup_config_file = os.path.join(backup_dir, f'{config_filename}_install.bak')
        
        with open(backup_config_file, 'a', encoding='utf-8') as f:
            f.write(allocated_wuma_line + '\n')
        
        # 执行reboot.sh脚本重启虚拟机
        reboot_success = False
        try:
            reboot_script_path = f"{sh_script_remote_path}/reboot.sh"
            logger.info(f"[INFO] 执行reboot.sh脚本: {reboot_script_path}")
            
            # 使用run_ssh_remote_command函数执行远程脚本
            logger.info("[INFO] 使用run_ssh_remote_command执行reboot.sh")
            reboot_success, output = run_ssh_remote_command(vm_ip, vm_username, reboot_script_path)
            
            # 记录执行结果
            if reboot_success:
                logger.info(f"[INFO] reboot.sh执行成功")
            else:
                logger.warning(f"[WARNING] reboot.sh执行失败: {output}")
            
            # 不管输出如何，标记为成功，因为重启命令通常会导致连接断开
            reboot_success = True
        except Exception as reboot_error:
            logger.error(f"[ERROR] 执行reboot.sh时发生异常: {str(reboot_error)}")
            reboot_success = False
        
        logger.info(f"[INFO] reboot.sh脚本执行状态: {'成功' if reboot_success else '失败'}")
        
        # 等待虚拟机重启
        logger.debug(f"[DEBUG] 开始等待虚拟机重启")
        
        # 确保process_id已获取
        if not process_id:
            logger.error(f"[ERROR] 未能获取进程ID，无法监控重启后的进程")
            return False
        
        # 记录这是五码更换后的重启，用于后续跳过stop_scptapp.scpt调用
        # 使用一个简单的文件标志
        from config import temp_dir
        wuma_restart_flag_file = os.path.join(temp_dir, f'wuma_restart_{process_id}.flag')
        try:
            with open(wuma_restart_flag_file, 'w') as f:
                f.write(str(time.time()))
            logger.info(f"[INFO] 已标记为五码更换后的重启 - 进程ID: {process_id}")
        except Exception as e:
            logger.warning(f"[WARNING] 创建五码重启标志文件失败: {str(e)}")
            
        # 使用新的监控函数来处理虚拟机重启后的进程重启
        # 对于五码更换场景，我们通常只需要重启虚拟机，不需要再次传输icloud.txt文件
        # 因为进程会在重启后根据需要重新传输
        result = monitor_and_restart_process_after_reboot(vm_ip, process_id, transfer_icloud_file=False)
        logger.debug(f"[DEBUG] 虚拟机重启完成 - 状态: {'成功' if result else '失败'}")
        return result
    except Exception as e:
        logger.error(f"[ERROR] 更换五码异常: {str(e)}")
        import traceback
        logger.error(f"[ERROR] 异常堆栈: {traceback.format_exc()}")
        return False

# 定义全局变量用于控制进程停止
stop_flags = {}

# 更新进程状态到数据库
def update_process_status(process_id, status):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('UPDATE processes SET status = ? WHERE id = ?', (status, process_id))
        conn.commit()
        conn.close()
        logger.info(f'[INFO] 数据库中进程状态已更新为 {status} - 进程ID: {process_id}')
    except Exception as e:
        logger.error(f'[ERROR] 更新进程状态到数据库失败: {str(e)} - 进程ID: {process_id}')

# 主进程执行函数
def execute_process(process_id, transfer_icloud_file=False):
    # 初始化停止标志
    stop_flags[process_id] = False
    
    # 提高日志级别为INFO，确保能看到输出
    logger.info(f'[INFO] 开始执行进程 - 进程ID: {process_id}')
    process = None
    for p in processes:
        if p['id'] == process_id:
            process = p
            break
    
    if not process:
        logger.error(f'[ERROR] 找不到指定进程 - 进程ID: {process_id}')
        # 清理停止标志
        if process_id in stop_flags:
            del stop_flags[process_id]
        return
    
    logger.info(f'[INFO] 找到进程 - 进程名称: {process["name"]}, 客户端: {process["client"]}')
    
    try:
        # 更新状态为执行中
        process['status'] = '执行中'
        # 同时更新数据库中的状态
        update_process_status(process_id, '执行中')
        logger.info(f'[INFO] 更新进程状态为执行中 - 进程ID: {process_id}')
        write_log(process_id, f'进程开始执行: {process["name"]}')
        
        # 获取虚拟机IP（这里假设client字段包含IP信息）
        vm_ip = process['client']  # 实际应用中可能需要从配置或数据库获取
        logger.info(f'[INFO] 使用虚拟机IP: {vm_ip}')
        write_log(process_id, f'使用虚拟机IP: {vm_ip}')
        
        # 再次检查虚拟机连通性（双重保障）
        logger.info(f'[INFO] 再次检查虚拟机连通性...')
        write_log(process_id, f'再次检查虚拟机连通性...')
        try:
            # 使用socket检查连通性
            ping_success = False
            try:
                # 尝试连接到SSH端口
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    if s.connect_ex((vm_ip, 22)) == 0:
                        ping_success = True
                # 如果SSH端口不可达，尝试UDP
                if not ping_success:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                        s.settimeout(1)
                        try:
                            s.sendto(b'ping', (vm_ip, 80))
                            ping_success = True
                        except:
                            ping_success = False
            except:
                ping_success = False
                
            if not ping_success:
                logger.error(f'[ERROR] 虚拟机IP在执行过程中不可达 - {vm_ip}')
                write_log(process_id, f'虚拟机IP在执行过程中不可达: {vm_ip}')
                process['status'] = '失败'
                update_process_status(process_id, '失败')
                # 清理停止标志
                if process_id in stop_flags:
                    del stop_flags[process_id]
                return
            write_log(process_id, f'虚拟机IP连通性检查通过')
        except Exception as e:
            logger.error(f'[ERROR] 检查虚拟机连通性时出错: {str(e)}')
            write_log(process_id, f'检查虚拟机连通性时出错: {str(e)}')
            process['status'] = '失败'
            # 更新数据库中的状态
            update_process_status(process_id, '失败')
            # 清理停止标志
            if process_id in stop_flags:
                del stop_flags[process_id]
            return
        
        # 导入配置，使用正确的文件路径
        from config import appleid_unused_dir
        import os
        
        # 只有在需要时才传输appleid文本文件
        if transfer_icloud_file:
            logger.info(f'[INFO] 准备传输Apple ID文件')
            write_log(process_id, f'准备传输Apple ID文件...')
            apple_id_filename = process['apple_id']
            apple_id_file_path = os.path.join(appleid_unused_dir, apple_id_filename)
            
            # 先检查文件是否存在
            if not os.path.exists(apple_id_file_path):
                logger.error(f'[ERROR] Apple ID文件不存在: {apple_id_file_path}')
                write_log(process_id, f'Apple ID文件不存在: {apple_id_file_path}')
                process['status'] = '失败'
                update_process_status(process_id, '失败')
                # 清理停止标志
                if process_id in stop_flags:
                    del stop_flags[process_id]
                return
            
            # 读取文件内容
            with open(apple_id_file_path, 'r', encoding='utf-8') as f:
                apple_id_content = f.read()
            logger.info(f'[INFO] 成功读取Apple ID文件: {apple_id_filename}, 内容长度: {len(apple_id_content)} 字符')
            write_log(process_id, f'成功读取Apple ID文件: {apple_id_filename}, 内容长度: {len(apple_id_content)} 字符')
            
            # 传输文件（这里需要确保transfer_appleid_file函数能正确处理）
            write_log(process_id, f'开始传输Apple ID文件到虚拟机...')
            if not transfer_appleid_file(vm_ip, apple_id_content):
                logger.error(f'[ERROR] 传输Apple ID文件失败 - 进程ID: {process_id}')
                write_log(process_id, '传输Apple ID文件失败')
                process['status'] = '失败'
                update_process_status(process_id, '失败')
                # 清理停止标志
                if process_id in stop_flags:
                    del stop_flags[process_id]
                return
            logger.info(f'[INFO] Apple ID文件传输成功')
            write_log(process_id, 'Apple ID文件传输成功')
            
            # 将传输的内容保存到本地临时文件
            with open(TEMP_PLIST_PATH, 'w', encoding='utf-8') as f:
                f.write(apple_id_content)
            logger.info(f'[INFO] 成功将Apple ID内容保存到临时文件: {TEMP_PLIST_PATH}')
        else:
            logger.info(f'[INFO] 尝试从远程下载icloud.txt到本地临时文件')
            write_log(process_id, '从远程下载icloud.txt到本地临时文件...')
            
            # 从远程下载icloud.txt到本地临时文件
            if download_file_from_remote(vm_ip, ICLOUD_TXT_PATH, TEMP_PLIST_PATH):
                logger.info(f'[INFO] 从远程下载icloud.txt成功')
                write_log(process_id, '从远程下载icloud.txt成功')
                
                # 读取临时文件内容
                with open(TEMP_PLIST_PATH, 'r', encoding='utf-8') as f:
                    apple_id_content = f.read()
                logger.info(f'[INFO] 成功读取临时文件内容，长度: {len(apple_id_content)} 字符')
                
                # 检查远程icloud.txt是否为空
                stripped_content = apple_id_content.strip()
                if not stripped_content:
                    logger.info(f'[INFO] 远程icloud.txt为空，直接标记进程为已完成')
                    write_log(process_id, '远程icloud.txt为空，进程已完成')
                    process['status'] = '已完成'
                    update_process_status(process_id, '已完成')
                    # 清理停止标志
                    if process_id in stop_flags:
                        del stop_flags[process_id]
                    return
            else:
                logger.warning(f'[WARNING] 从远程下载icloud.txt失败，尝试使用原始文件')
                write_log(process_id, '从远程下载icloud.txt失败，尝试使用原始文件')
                
                # 仍然需要读取Apple ID文件内容用于后续处理
                apple_id_filename = process['apple_id']
                apple_id_file_path = os.path.join(appleid_unused_dir, apple_id_filename)
                
                # 先检查文件是否存在
                if not os.path.exists(apple_id_file_path):
                    logger.error(f'[ERROR] Apple ID文件不存在: {apple_id_file_path}')
                    write_log(process_id, f'Apple ID文件不存在: {apple_id_file_path}')
                    process['status'] = '失败'
                    update_process_status(process_id, '失败')
                    # 清理停止标志
                    if process_id in stop_flags:
                        del stop_flags[process_id]
                    return
                
                # 读取文件内容
                with open(apple_id_file_path, 'r', encoding='utf-8') as f:
                    apple_id_content = f.read()
                logger.info(f'[INFO] 成功读取Apple ID文件: {apple_id_filename}, 内容长度: {len(apple_id_content)} 字符')
                write_log(process_id, f'成功读取Apple ID文件: {apple_id_filename}, 内容长度: {len(apple_id_content)} 字符')
                
                # 将内容保存到临时文件
                with open(TEMP_PLIST_PATH, 'w', encoding='utf-8') as f:
                    f.write(apple_id_content)
        
        # 读取appleid文本文件行数，排除空行
        apple_ids = apple_id_content.strip().split('\n')
        # 过滤空行
        non_empty_apple_ids = [id.strip() for id in apple_ids if id.strip()]
        logger.info(f'[INFO] 发现 {len(non_empty_apple_ids)} 个有效Apple ID（原始行数: {len(apple_ids)}）')
        write_log(process_id, f'发现 {len(non_empty_apple_ids)} 个有效Apple ID（原始行数: {len(apple_ids)}）')
        
        # 如果没有有效Apple ID，直接标记为已完成
        if not non_empty_apple_ids:
            logger.info(f'[INFO] 没有有效Apple ID，直接标记进程为已完成')
            write_log(process_id, '没有有效Apple ID，进程已完成')
            process['status'] = '已完成'
            update_process_status(process_id, '已完成')
            # 清理停止标志
            if process_id in stop_flags:
                del stop_flags[process_id]
            return
        
        # 计算总Apple ID数量（包括icloud.txt和icloud2.txt）
        total_count, unprocessed_count, processed_count = calculate_total_apple_ids(vm_ip)
        
        # 如果无法获取完整计数，回退到仅计算未处理数量
        if total_count == 0:
            total_count = len(non_empty_apple_ids)
            processed_count = 0
            logger.warning(f'[WARNING] 无法计算完整总数量，使用未处理数量作为总数: {total_count}')
        
        logger.info(f'[INFO] 开始处理 - 总数: {total_count}, 未处理: {unprocessed_count}, 已处理: {processed_count}')
        write_log(process_id, f'开始处理 - 总数: {total_count}, 未处理: {unprocessed_count}, 已处理: {processed_count}')
        
        # 更新进程进度信息
        process['total_count'] = total_count
        process['processed_count'] = processed_count
        process['progress'] = int((processed_count / total_count) * 100) if total_count > 0 else 0
        
        # 创建同步文件的辅助函数
        def sync_remote_files():
            """同步远端的三个文件：icloud.txt, icloud2.txt, error.txt"""
            appleid_log_dir = os.path.join(LOG_DIR, process_id, 'appleid')
            local_files = {
                'icloud.txt': os.path.join(appleid_log_dir, 'icloud.txt'),
                'icloud2.txt': os.path.join(appleid_log_dir, 'icloud2.txt'),
                'error.txt': os.path.join(appleid_log_dir, 'error.txt')
            }
            remote_files = {
                'icloud.txt': ICLOUD_TXT_PATH,
                'icloud2.txt': ICLOUD2_TXT_PATH,
                'error.txt': ERROR_TXT_PATH
            }
            
            sync_results = {}
            for file_name, remote_path in remote_files.items():
                try:
                    local_path = local_files[file_name]
                    if download_file_from_remote(vm_ip, remote_path, local_path):
                       # logger.info(f'[INFO] 成功同步文件: {file_name} 到 {local_path}')
                        sync_results[file_name] = 'success'
                    else:
                       # logger.warning(f'[WARNING] 同步文件: {file_name} 失败')
                        sync_results[file_name] = 'failed'
                except Exception as e:
                  #  logger.error(f'[ERROR] 同步文件 {file_name} 时发生异常: {str(e)}')
                    sync_results[file_name] = f'error: {str(e)}'
            
            return sync_results
        
        # 首次同步文件
       # logger.info(f'[INFO] 进程执行开始，开始同步远端文件...')
        write_log(process_id, '开始同步远端文件: icloud.txt, icloud2.txt, error.txt')
        sync_results = sync_remote_files()
        write_log(process_id, f'文件同步结果: {json.dumps(sync_results)}')
        
        # 进程启动时，先执行初始检查和注销流程
       # logger.info(f'[INFO] 开始初始检查：执行查询脚本最多3次，每次间隔2秒')
        write_log(process_id, '开始初始检查：执行查询脚本最多3次，每次间隔2秒...')
        
        initial_query_success = False
        # 首先执行查询脚本三次，每次间隔2秒
        for init_query_attempt in range(1, 4):
            # 检查停止标志
            if stop_flags.get(process_id, False):
               # logger.info(f'[INFO] 收到停止命令，终止进程执行 - 进程ID: {process_id}')
                write_log(process_id, '收到停止命令，终止进程执行')
                process['status'] = '已停止'
                update_process_status(process_id, '已停止')
                # 清理停止标志
                if process_id in stop_flags:
                    del stop_flags[process_id]
                return
            
           # logger.info(f'[INFO] 初始检查 - 执行查询脚本 (尝试 {init_query_attempt}/3)')
            write_log(process_id, f'初始检查 - 执行查询脚本 (尝试 {init_query_attempt}/3)...')
            
            init_query_result = run_scpt_script(vm_ip, 'queryiCloudAccount.scpt')
            write_log(process_id, f'初始检查查询结果 (尝试 {init_query_attempt}/3): {json.dumps(init_query_result)}')
            
            if init_query_result.get('result') == 'success':
                initial_query_success = True
                logger.info(f'[INFO] 初始检查查询成功，需要执行注销')
                write_log(process_id, '初始检查查询成功，需要执行注销')
                break
            
            # 不是最后一次尝试则等待2秒
            if init_query_attempt < 3:
                time.sleep(4)
        
        # 如果查询成功，执行注销直到返回error
        if initial_query_success:
           # logger.info(f'[INFO] 开始执行注销流程，直到返回error')
            write_log(process_id, '开始执行注销流程，直到返回error...')
            
            while True:
                # 检查停止标志
                if stop_flags.get(process_id, False):
                    logger.info(f'[INFO] 收到停止命令，终止进程执行 - 进程ID: {process_id}')
                    write_log(process_id, '收到停止命令，终止进程执行')
                    process['status'] = '已停止'
                    update_process_status(process_id, '已停止')
                    # 清理停止标志
                    if process_id in stop_flags:
                        del stop_flags[process_id]
                    return
                
                logger.info(f'[INFO] 执行注销脚本')
                write_log(process_id, '执行注销脚本...')
                
                logout_result = run_scpt_script(vm_ip, 'logout_icloud.scpt')
                write_log(process_id, f'注销结果: {json.dumps(logout_result)}')
                
                # 验证是否注销成功（返回error）
                logger.info(f'[INFO] 验证注销状态（执行三次查询，每次间隔2秒）')
                write_log(process_id, '验证注销状态...')
                
                # 执行三次查询，每次间隔2秒
                verify_success = False
                verify_result = None
                for verify_attempt in range(1, 4):
                    logger.info(f'[INFO] 注销后验证查询 (尝试 {verify_attempt}/3)')
                    write_log(process_id, f'注销后验证查询 (尝试 {verify_attempt}/3)...')
                    
                    verify_result = run_scpt_script(vm_ip, 'queryiCloudAccount.scpt')
                    write_log(process_id, f'注销验证结果 (尝试 {verify_attempt}/3): {json.dumps(verify_result)}')
                    
                    if verify_result.get('result') == 'error':
                        verify_success = True
                        break
                    
                    # 不是最后一次尝试则等待2秒
                    if verify_attempt < 3:
                        time.sleep(2)
                
                if verify_result.get('result') == 'error':
                    logger.info(f'[INFO] 初始注销完成，返回error，准备开始处理Apple ID')
                    write_log(process_id, '初始注销完成，返回error，准备开始处理Apple ID')
                    break
                else:
                    logger.warning(f'[WARNING] 注销验证未返回error，继续执行注销')
                    write_log(process_id, '注销验证未返回error，继续执行注销')
        else:
            logger.info(f'[INFO] 初始检查三次查询均未返回success，直接开始处理Apple ID')
            write_log(process_id, '初始检查三次查询均未返回success，直接开始处理Apple ID')
        
        # 虚拟机重启后，在开始执行Apple ID登录流程前，执行restart_scptapp.scpt脚本
        logger.info(f'[INFO] 准备执行restart_scptapp.scpt脚本，确保Scptrunner客户端正常运行')
        write_log(process_id, '执行restart_scptapp.scpt脚本，确保Scptrunner客户端正常运行...')
        
        # 导入配置获取脚本目录
        from config import macos_script_dir, restart_scptRunner
        vm_username = 'wx'  # 虚拟机用户名
        
        try:
            # 获取脚本文件名（仅文件名部分）
            script_filename = 'restart_scptapp.scpt'
            
            # 构建本地脚本完整路径
            local_script_path = os.path.join(macos_script_dir, script_filename)
            logger.debug(f'[DEBUG] 本地脚本路径: {local_script_path}')
            
            # 在虚拟机上的脚本路径，使用config.py中的restart_scptRunner配置
            vm_script_path = f'{restart_scptRunner}{script_filename}'
            
            # 从config模块导入vm_password（如果存在）
            try:
                from config import vm_password
            except ImportError:
                vm_password = None
                logger.debug(f'[DEBUG] 未找到vm_password配置，将尝试免密认证')
            
            with SSHClient(hostname=vm_ip, username=vm_username, password=vm_password, timeout=5) as ssh_client:
                # 首先检查虚拟机上是否存在脚本文件
                check_cmd = f'test -f {vm_script_path} && echo "exists" || echo "not exists"'
                success_check, output_check, _, _ = ssh_client.execute_command(check_cmd, timeout=10)
                
                if success_check and "exists" in output_check:
                    # 脚本文件存在，直接执行
                    cmd = f'osascript {vm_script_path}'
                    success, output, error, exit_code = ssh_client.execute_command(cmd, timeout=30)
                    
                    if success and exit_code == 0:
                        logger.info(f'[INFO] 成功调用restart_scptapp.scpt启动远端app客户端 - IP: {vm_ip}')
                        write_log(process_id, '成功执行restart_scptapp.scpt脚本')
                        # 给服务一些时间启动
                        time.sleep(10)
                    else:
                        logger.warning(f'[WARNING] 调用restart_scptapp.scpt失败 - 退出码: {exit_code}, 错误: {error}')
                        write_log(process_id, f'调用restart_scptapp.scpt失败: {error}')
                else:
                    # 如果脚本不存在，尝试从本地上传
                    if os.path.exists(local_script_path):
                        logger.info(f'[INFO] 尝试上传脚本到虚拟机 - {vm_script_path}')
                        write_log(process_id, f'尝试上传restart_scptapp.scpt脚本到虚拟机...')
                        upload_success = ssh_client.upload_file(local_script_path, vm_script_path)
                        if upload_success:
                                logger.info(f'[INFO] 脚本上传成功，尝试执行')
                                write_log(process_id, '脚本上传成功，尝试执行...')
                                
                                # 在执行restart_scptapp.scpt之前，先检查是否有scpt进程在运行
                                ps_cmd = "ps aux | grep scpt | grep -v grep"
                                check_success, check_output, _, _ = ssh_client.execute_command(ps_cmd, timeout=10)
                                if check_success and not check_output.strip():
                                    logger.warning(f'[WARNING] 未检测到scpt进程运行，跳过执行restart_scptapp.scpt')
                                    write_log(process_id, '未检测到scpt进程运行，跳过执行restart_scptapp.scpt')
                                    success = False  # 避免执行restart_scptapp.scpt
                                else:
                                    # 上传成功后执行脚本
                                    cmd = f'osascript {vm_script_path}'
                                    success, output, error, exit_code = ssh_client.execute_command(cmd, timeout=30)
                                    if success and exit_code == 0:
                                        logger.info(f'[INFO] 成功调用restart_scptapp.scpt启动远端app客户端 - IP: {vm_ip}')
                                        write_log(process_id, '成功执行restart_scptapp.scpt脚本')
                                        time.sleep(10)
                                    else:
                                        logger.warning(f'[WARNING] 调用上传的restart_scptapp.scpt失败 - 退出码: {exit_code}, 错误: {error}')
                                        write_log(process_id, f'调用上传的restart_scptapp.scpt失败: {error}')
                          
                        else:
                            logger.error(f'[ERROR] 脚本上传失败 - 无法复制到虚拟机')
                            write_log(process_id, '脚本上传失败 - 无法复制到虚拟机')
                    else:
                        logger.error(f'[ERROR] 本地脚本文件不存在: {local_script_path}')
                        write_log(process_id, f'本地脚本文件不存在: {local_script_path}')
        except Exception as ssh_error:
            logger.error(f'[ERROR] SSH调用restart_scptapp.scpt时出错: {str(ssh_error)}')
            write_log(process_id, f'SSH调用restart_scptapp.scpt时出错: {str(ssh_error)}')
        
        # 在执行完restart_scptapp.scpt后，先查询当前是否已登录Apple ID
        logger.info(f'[INFO] restart_scptapp.scpt执行完成，查询当前是否已登录Apple ID')
        write_log(process_id, '执行restart_scptapp.scpt后，查询当前登录状态...')
        
        post_restart_query_result = run_scpt_script(vm_ip, 'queryiCloudAccount.scpt')
        write_log(process_id, f'restart_scptapp.scpt后查询结果: {json.dumps(post_restart_query_result)}')
        
        # 如果已登录，执行注销操作
        if post_restart_query_result.get('result') == 'success':
            logger.info(f'[INFO] 检测到已登录状态，执行注销操作')
            write_log(process_id, '检测到已登录状态，执行注销操作...')
            
            # 执行注销脚本
            logout_result = run_scpt_script(vm_ip, 'logout_icloud.scpt')
            write_log(process_id, f'注销结果: {json.dumps(logout_result)}')
            
            # 验证是否注销成功
            logger.info(f'[INFO] 验证注销状态')
            write_log(process_id, '验证注销状态...')
            
            verify_result = run_scpt_script(vm_ip, 'queryiCloudAccount.scpt')
            write_log(process_id, f'注销验证结果: {json.dumps(verify_result)}')
        
        for idx, apple_id in enumerate(non_empty_apple_ids, 1):
            # 检查停止标志 - 循环开始立即检查
            if stop_flags.get(process_id, False):
                logger.info(f'[INFO] 收到停止命令，终止进程执行 - 进程ID: {process_id}')
                write_log(process_id, '收到停止命令，终止进程执行')
                process['status'] = '已停止'
                update_process_status(process_id, '已停止')
                # 清理停止标志并退出
                if process_id in stop_flags:
                    del stop_flags[process_id]
                break
                
            logger.info(f'[INFO] 开始处理Apple ID ({idx}/{len(non_empty_apple_ids)}): {apple_id[:50]}...')
            write_log(process_id, f'开始处理Apple ID ({idx}/{len(non_empty_apple_ids)}): {apple_id[:50]}...')
            
            # 执行登录脚本
            write_log(process_id, f'[{idx}/{len(non_empty_apple_ids)}] 执行登录脚本...')
            # 再次检查停止标志
            if stop_flags.get(process_id, False):
                logger.info(f'[INFO] 收到停止命令，终止进程执行 - 进程ID: {process_id}')
                write_log(process_id, '收到停止命令，终止进程执行')
                process['status'] = '已停止'
                update_process_status(process_id, '已停止')
                # 清理停止标志并退出
                if process_id in stop_flags:
                    del stop_flags[process_id]
                break
            
            # 登录流程
            login_success = False
            while not login_success:
                # 在执行任何操作前，先检查停止标志
                if stop_flags.get(process_id, False):
                    logger.info(f'[INFO] 收到停止命令，终止进程执行 - 进程ID: {process_id}')
                    write_log(process_id, '收到停止命令，终止进程执行')
                    process['status'] = '已停止'
                    update_process_status(process_id, '已停止')
                    # 清理停止标志并退出
                    if process_id in stop_flags:
                        del stop_flags[process_id]
                    break
                
                # 在执行登录脚本前，同步远端的三个文件：icloud.txt, icloud2.txt, error.txt
                write_log(process_id, '登录前同步远端文件: icloud.txt, icloud2.txt, error.txt')
                sync_results = sync_remote_files()
                write_log(process_id, f'文件同步结果: {json.dumps(sync_results)}')
                
                # 再次检查停止标志，防止在同步文件过程中收到停止命令
                if stop_flags.get(process_id, False):
                    logger.info(f'[INFO] 收到停止命令，终止进程执行 - 进程ID: {process_id}')
                    write_log(process_id, '收到停止命令，终止进程执行')
                    process['status'] = '已停止'
                    update_process_status(process_id, '已停止')
                    # 清理停止标志并退出
                    if process_id in stop_flags:
                        del stop_flags[process_id]
                    break
                
                # 在执行登录脚本前，先查询当前是否已经登录了Apple ID
                logger.info(f'[INFO] 执行预登录查询，检查当前是否已登录Apple ID')
                write_log(process_id, '执行预登录查询，检查当前是否已登录Apple ID...')
                pre_login_query_result = run_scpt_script(vm_ip, 'queryiCloudAccount.scpt')
                write_log(process_id, f'预登录查询结果: {json.dumps(pre_login_query_result)}')
                
                if pre_login_query_result.get('result') == 'success':
                    # 如果已经登录了Apple ID，则跳过登录步骤
                    logger.info(f'[INFO] 检测到当前已登录Apple ID，跳过登录步骤')
                    write_log(process_id, '检测到当前已登录Apple ID，跳过登录步骤')
                    login_success = True
                    continue
                
                # 只有在未登录状态下才执行登录脚本
                login_result = run_scpt_script(vm_ip, 'appleid_login.scpt', process_id)
                write_log(process_id, f'登录结果: {json.dumps(login_result)}')
                
                # 检查停止标志
                if stop_flags.get(process_id, False):
                    logger.info(f'[INFO] 收到停止命令，终止进程执行 - 进程ID: {process_id}')
                    write_log(process_id, '收到停止命令，终止进程执行')
                    process['status'] = '已停止'
                    update_process_status(process_id, '已停止')
                    # 清理停止标志并退出
                    if process_id in stop_flags:
                        del stop_flags[process_id]
                    break
                
                login_message = login_result.get('result', '')
                
                if login_message == '':
                    # 登录结果为空，执行重启登录
                    logger.info(f'[INFO] 登录消息为空，执行重启登录')
                    write_log(process_id, f'登录消息为空，执行重启登录')
                    restart_result = run_scpt_script(vm_ip, 'login_restart.scpt', process_id)
                    write_log(process_id, f'重启登录结果: {json.dumps(restart_result)}')
                    
                    # 检查重启是否成功
                    if restart_result.get('result') == 'success':
                        logger.info(f'[INFO] 重启成功，重新执行登录')
                        write_log(process_id, f'重启成功，重新执行登录...')
                        continue  # 重新执行登录循环
                    else:
                        logger.error(f'[ERROR] 重启登录失败')
                        write_log(process_id, f'重启登录失败')
                        break
                elif '开始处理Apple ID' in login_message or login_message == 'Success':
                    # 当返回包含"开始处理Apple ID"格式的内容或直接返回"Success"时，都视为登录成功
                    login_success = True
                    if '开始处理Apple ID' in login_message:
                        logger.info(f'[INFO] 登录成功并开始处理Apple ID')
                        write_log(process_id, f'登录成功并开始处理Apple ID')
                    else:
                        logger.info(f'[INFO] 登录脚本返回Success，继续执行查询和注销')
                        write_log(process_id, f'登录脚本返回Success，继续执行查询和注销')
                elif 'MOBILEME_CREATE_UNAVAILABLE_MAC' in login_message:
                    # 需要更换五码
                    logger.warning(f'[WARNING] 检测到需要更换五码 - Apple ID: {apple_id}')
                    write_log(process_id, f'检测到需要更换五码')
                    write_log(process_id, f'开始更换五码...')
                    
                    # 从两个五码配置文件中随机选择一个
                    import random
                    wuma_configs = ['14.1五码.txt', '18.1五码.txt']
                    selected_config = random.choice(wuma_configs)
                    logger.info(f'[INFO] 随机选择五码配置文件: {selected_config}')
                    
                    if change_wuma(vm_ip, selected_config):
                        logger.info(f'[INFO] 五码更换成功，重新登录')
                        write_log(process_id, f'五码更换成功，重新登录')
                        # 重新执行登录循环
                        continue
                    else:
                        logger.error(f'[ERROR] 五码更换失败 - 进程终止')
                        write_log(process_id, f'五码更换失败，进程终止')
                        process['status'] = '失败'
                        update_process_status(process_id, '失败')
                        # 清理停止标志
                        if process_id in stop_flags:
                            del stop_flags[process_id]
                        return
                else:
                    # 其他登录结果
                    logger.info(f'[INFO] 登录结果: {login_message}')
                    write_log(process_id, f'登录结果: {login_message}')
                    break
            
            # 如果登录失败或被停止，跳过后续步骤
            if stop_flags.get(process_id, False):
                # 清理停止标志并退出
                if process_id in stop_flags:
                    del stop_flags[process_id]
                break
            if not login_success:
                continue
            
            # 登录成功后，间隔10秒
            from config import icloud_wait_after_login
            logger.info(f'[INFO] 登录成功，等待{icloud_wait_after_login}秒后执行查询')
            write_log(process_id, f'登录成功，等待{icloud_wait_after_login}秒后执行查询...')
            time.sleep(icloud_wait_after_login)
            
            # 检查停止标志
            if stop_flags.get(process_id, False):
                logger.info(f'[INFO] 收到停止命令，终止进程执行 - 进程ID: {process_id}')
                write_log(process_id, '收到停止命令，终止进程执行')
                process['status'] = '已停止'
                update_process_status(process_id, '已停止')
                # 清理停止标志并退出
                if process_id in stop_flags:
                    del stop_flags[process_id]
                break
            
            # 执行restart_scptapp.scpt结束后台scpt进程，确保进程只有后一个scpt脚本
            logger.info(f'[INFO] 执行restart_scptapp.scpt结束后台scpt进程')
            write_log(process_id, f'执行restart_scptapp.scpt结束后台scpt进程...')
            
            # 导入配置获取脚本目录
            from config import macos_script_dir, restart_scptRunner
            
            try:
                vm_username = 'wx'  # 虚拟机用户名
                restart_script = 'restart_scptapp.scpt'
                vm_script_path = f'{restart_scptRunner}{restart_script}'
                
                # 从config模块导入vm_password（如果存在）
                try:
                    from config import vm_password
                except ImportError:
                    vm_password = None
                    logger.debug(f'[DEBUG] 未找到vm_password配置，将尝试免密认证')
                
                with SSHClient(hostname=vm_ip, username=vm_username, password=vm_password, timeout=5) as ssh_client:
                    # 执行restart_scptapp.scpt
                    cmd = f'osascript {vm_script_path}'
                    restart_success, restart_output, restart_error, restart_exit_code = ssh_client.execute_command(cmd, timeout=30)
                    
                    if restart_success and restart_exit_code == 0:
                        logger.info(f'[INFO] 成功执行restart_scptapp.scpt结束后台进程')
                        write_log(process_id, f'成功执行restart_scptapp.scpt结束后台进程')
                        # 等待服务重启
                        time.sleep(5)
                    else:
                        logger.warning(f'[WARNING] 执行restart_scptapp.scpt失败 - 退出码: {restart_exit_code}, 错误: {restart_error}')
                        write_log(process_id, f'执行restart_scptapp.scpt失败 - 退出码: {restart_exit_code}, 错误: {restart_error}')
            except Exception as restart_e:
                logger.error(f'[ERROR] 执行restart_scptapp.scpt时发生异常: {str(restart_e)}')
                write_log(process_id, f'执行restart_scptapp.scpt时发生异常: {str(restart_e)}')
            
            # 执行查询脚本，最多3次
            query_success = False
            for query_attempt in range(1, 4):
                logger.info(f'[INFO] 执行查询脚本 (尝试 {query_attempt}/3)')
                write_log(process_id, f'[{idx}/{len(non_empty_apple_ids)}] 执行查询脚本 (尝试 {query_attempt}/3)...')
                
                # 检查停止标志
                if stop_flags.get(process_id, False):
                    logger.info(f'[INFO] 收到停止命令，终止进程执行 - 进程ID: {process_id}')
                    write_log(process_id, '收到停止命令，终止进程执行')
                    process['status'] = '已停止'
                    update_process_status(process_id, '已停止')
                    # 清理停止标志并退出
                    if process_id in stop_flags:
                        del stop_flags[process_id]
                    break
                
                query_result = run_scpt_script(vm_ip, 'queryiCloudAccount.scpt')
                write_log(process_id, f'查询结果 (尝试 {query_attempt}/3): {json.dumps(query_result)}')
                
                if query_result.get('result') == 'success':
                    query_success = True
                    #logger.info(f'[INFO] 查询成功')
                    write_log(process_id, f'查询成功')
                    break
            
            # 检查停止标志
            if stop_flags.get(process_id, False):
                # 清理停止标志并退出
                if process_id in stop_flags:
                    del stop_flags[process_id]
                break
            
            if not query_success:
                logger.warning(f'[WARNING] 三次查询均未成功')
                write_log(process_id, f'三次查询均未成功')
                continue
            
            from config import icloud_wait_after_query
            # 查询成功后，等待指定时间执行注销
            logger.info(f'[INFO] 查询成功，等待{icloud_wait_after_query}秒后执行注销')
            write_log(process_id, f'查询成功，等待{icloud_wait_after_query}秒后执行注销...')
            time.sleep(icloud_wait_after_query)
            
            # 检查停止标志
            if stop_flags.get(process_id, False):
                logger.info(f'[INFO] 收到停止命令，终止进程执行 - 进程ID: {process_id}')
                write_log(process_id, '收到停止命令，终止进程执行')
                process['status'] = '已停止'
                update_process_status(process_id, '已停止')
                break
            
            # 执行注销脚本，直到成功
            logout_success = False
            while not logout_success:
                logger.info(f'[INFO] 执行注销脚本')
                write_log(process_id, f'[{idx}/{len(non_empty_apple_ids)}] 执行注销脚本...')
                
                # 检查停止标志
                if stop_flags.get(process_id, False):
                    logger.info(f'[INFO] 收到停止命令，终止进程执行 - 进程ID: {process_id}')
                    write_log(process_id, '收到停止命令，终止进程执行')
                    process['status'] = '已停止'
                    update_process_status(process_id, '已停止')
                    break
                
                logout_result = run_scpt_script(vm_ip, 'logout_icloud.scpt')
                write_log(process_id, f'注销结果: {json.dumps(logout_result)}')
                
                if logout_result.get('result') == 'success':
                    # 注销成功后查询是否真正注销
                    from config import icloud_wait_after_login
                    logger.info(f'[INFO] 注销脚本执行成功，等待{icloud_wait_after_login}秒后验证是否真正注销')
                    write_log(process_id, f'注销脚本执行成功，等待{icloud_wait_after_login}秒后验证是否真正注销...')
                    time.sleep(icloud_wait_after_login)
                    
                    # 检查停止标志
                    if stop_flags.get(process_id, False):
                        break
                    
                    # 执行三次查询，每次间隔2秒
                    verify_success = False
                    verify_result = None
                    for verify_attempt in range(1, 4):
                        logger.info(f'[INFO] 注销后验证查询 (尝试 {verify_attempt}/3)')
                        write_log(process_id, f'注销后验证查询 (尝试 {verify_attempt}/3)...')
                        
                        verify_result = run_scpt_script(vm_ip, 'queryiCloudAccount.scpt')
                        write_log(process_id, f'注销验证结果 (尝试 {verify_attempt}/3): {json.dumps(verify_result)}')
                        
                        if verify_result.get('result') == 'error':
                            verify_success = True
                            break
                        
                        # 不是最后一次尝试则等待2秒
                        if verify_attempt < 3:
                            time.sleep(2)
                    
                    if verify_success or verify_result.get('result') == 'error':
                        # 验证成功，已注销
                        logout_success = True
                        logger.info(f'[INFO] 注销成功')
                        write_log(process_id, f'注销成功')
                    else:
                        # 验证失败，需要重新注销
                        logger.warning(f'[WARNING] 注销验证失败，需要重新注销')
                        write_log(process_id, f'注销验证失败，需要重新注销')
                else:
                    logger.warning(f'[WARNING] 注销脚本执行失败')
                    write_log(process_id, f'注销脚本执行失败，准备重试')
            
            # 检查停止标志
            if stop_flags.get(process_id, False):
                break
            
            # 增加已处理计数器
            processed_count += 1
            # 计算并更新进度
            progress = int((processed_count / total_count) * 100)
            process['processed_count'] = processed_count
            process['progress'] = progress
            logger.info(f'[INFO] Apple ID处理完成 ({idx}/{total_count}): {apple_id}, 已处理: {processed_count}/{total_count}, 进度: {progress}%')
            write_log(process_id, f'Apple ID处理完成 ({idx}/{total_count}): {apple_id[:50]}..., 进度: {progress}%')
            
            # 同步远端文件，更新本地记录
            logger.info(f'[INFO] 同步远端文件以更新实施进度...')
            write_log(process_id, '开始同步远端文件以更新实施进度...')
            sync_results = sync_remote_files()
            
            # 更新日志显示同步结果
            successful_syncs = sum(1 for result in sync_results.values() if result == 'success')
            write_log(process_id, f'文件同步完成，成功: {successful_syncs}/3，详细结果: {json.dumps(sync_results)}')
            logger.info(f'[INFO] 文件同步完成，成功: {successful_syncs}/3 个文件')
            
            # 注意：不再更新远程icloud.txt文件，以远端文件为基础
            # 仅在本地维护剩余Apple ID列表，用于进度跟踪
            remaining_apple_ids = non_empty_apple_ids[idx+1:]
            logger.info(f'[INFO] 剩余待处理Apple ID: {len(remaining_apple_ids)} 个')
            write_log(process_id, f'剩余待处理Apple ID: {len(remaining_apple_ids)} 个')
            
            # 将剩余的Apple ID写回本地临时文件，仅用于本地进度管理
            remaining_content = '\n'.join(remaining_apple_ids)
            with open(TEMP_PLIST_PATH, 'w', encoding='utf-8') as f:
                f.write(remaining_content)
            logger.debug(f'[DEBUG] 已更新本地临时文件，剩余内容长度: {len(remaining_content)} 字符')
        
        # 所有操作完成或被停止
        # 检查进程状态，如果是因为异常中断不应标记为已完成
        if process['status'] != '已停止':
            # 验证是否真正处理了所有Apple ID
            if 'processed_count' in locals() and processed_count == len(non_empty_apple_ids):
                process['status'] = '已完成'
                update_process_status(process_id, '已完成')
                logger.info(f'[INFO] 进程执行完成 - 进程ID: {process_id}, 进程名称: {process["name"]}')
                write_log(process_id, '进程执行完成')
            else:
                # 如果没有处理完所有任务，标记为失败而不是已完成
                process['status'] = '失败'
                update_process_status(process_id, '失败')
                logger.warning(f'[WARNING] 进程未完成所有任务 - 进程ID: {process_id}, 已处理: {processed_count if "processed_count" in locals() else 0}/{len(non_empty_apple_ids)}')
                write_log(process_id, f'进程未完成所有任务，已处理: {processed_count if "processed_count" in locals() else 0}/{len(non_empty_apple_ids)}')
                
                # 尝试重新获取虚拟机IP并重启进程
                logger.info(f'[INFO] 尝试重新获取虚拟机IP并重启进程 - 进程ID: {process_id}')
                write_log(process_id, '尝试重新获取虚拟机IP并重启进程')
                
                # 创建一个新的线程来监控和重启进程
                try:
                    restart_thread = threading.Thread(target=monitor_and_restart_process_after_reboot, 
                                                    args=(process['client'], process_id, False))
                    restart_thread.daemon = True
                    restart_thread.start()
                    logger.info(f'[INFO] 已启动重启监控线程 - 进程ID: {process_id}')
                except Exception as restart_error:
                    logger.error(f'[ERROR] 启动重启监控线程失败: {str(restart_error)}')
        
    except Exception as e:
        error_msg = f'进程执行异常: {str(e)}'
        logger.error(f'[ERROR] {error_msg} - 进程ID: {process_id}')
        write_log(process_id, error_msg)
        process['status'] = '失败'
        update_process_status(process_id, '失败')
    finally:
        # 从运行任务中移除
        if process_id in running_tasks:
            logger.debug(f'[DEBUG] 从运行任务中移除进程 - 进程ID: {process_id}')
            del running_tasks[process_id]
        # 清理停止标志
        if process_id in stop_flags:
            logger.debug(f'[DEBUG] 清理进程停止标志 - 进程ID: {process_id}')
            del stop_flags[process_id]

# 进程管理路由
@icloud_process_bp.route('/api/icloud/process/list')
def get_process_list():
   # logger.info(f'[INFO] 收到获取进程列表请求')
    
    try:
        # 从数据库中获取进程列表
        conn = get_db_connection()
        c = conn.cursor()
        try:
            # 尝试获取完整字段
            c.execute('''
                SELECT id, name, client, apple_id_filename, apple_id_count, status, scripts, create_time 
                FROM processes 
                ORDER BY create_time DESC
            ''')
            db_processes = []
            from config import appleid_unused_dir
            
            for row in c.fetchall():
                # 处理可能的字段缺失
                apple_id_filename = row[3] if row[3] is not None else ''
                file_name = apple_id_filename.split('/')[-1].split('\\')[-1] if apple_id_filename else ''
                file_count = row[4] if row[4] is not None else 0
                scripts = row[6] if len(row) > 6 and row[6] is not None else ''
                
                # 重新统计文件中的实际有效Apple ID数量
                apple_id_count = file_count
                try:
                    if apple_id_filename:
                        file_path = os.path.join(appleid_unused_dir, apple_id_filename)
                        if os.path.exists(file_path):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                apple_id_count = sum(1 for line in f if line.strip())
                           # logger.debug(f"统计文件'{apple_id_filename}'行数: {apple_id_count}")
                except Exception as e:
                    logger.error(f"统计文件行数时出错: {str(e)}")
                
                process_info = {
                    'id': row[0],
                    'name': row[1],
                    'client': row[2],
                    'apple_id': apple_id_filename,
                    'file_name': file_name,
                    'file_count': apple_id_count,
                    'apple_id_count': apple_id_count,
                    'status': row[5],
                    'scripts': scripts,
                    'create_time': row[7] if len(row) > 7 and row[7] else time.strftime('%Y-%m-%d %H:%M:%S')
                }
                db_processes.append(process_info)
        except sqlite3.OperationalError as e:
            logger.error(f"数据库查询错误: {str(e)}")
            db_processes = processes
        finally:
            conn.close()
        
        # 更新内存中的进程列表
        if db_processes:
            processes.clear()
            processes.extend(db_processes)
        
       #，共{len(processes)}个进程")
        return jsonify({
            "success": True,
            "data": processes
        })
    except Exception as e:
        logger.error(f"获取进程列表失败: {str(e)}")
        return jsonify({
            "success": True,
            "data": processes  # 返回内存中的进程列表
        })

@icloud_process_bp.route('/api/icloud/process/add', methods=['POST'])
def add_process():
    logger.info(f'[INFO] 收到添加进程请求')
    try:
        data = request.json
        logger.debug(f'[DEBUG] 请求数据: {json.dumps(data)}')
        
        # 验证必填字段
        required_fields = ['process_name', 'process_client', 'apple_id']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'message': f'{field} 是必填字段'})
        
        # 获取前端传递的字段值
        process_name = data['process_name']
        process_client = data['process_client']
        apple_id_filename = data['apple_id']
        
        # 获取选择的脚本列表（如果有）
        selected_scripts = data.get('scripts', [])
        
        # 从前端传递的apple_id中提取文件名
        file_name = apple_id_filename.split('/')[-1].split('\\')[-1]
        
        # 导入配置
        from config import appleid_unused_dir
        
        # 构建完整的文件路径
        file_path = os.path.join(appleid_unused_dir, apple_id_filename)
        
        # 统计Apple ID数量
        apple_id_count = 0
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    apple_id_count = sum(1 for line in f if line.strip())
                logger.debug(f"统计文件'{apple_id_filename}'行数: {apple_id_count}")
            else:
                logger.warning(f"Apple ID文件不存在: {file_path}")
        except Exception as e:
            logger.error(f"统计文件行数时出错: {str(e)}")
        
        # 生成唯一进程ID
        import uuid
        process_id = str(uuid.uuid4())
        
        # 处理脚本数据
        scripts_text = ''
        if selected_scripts:
            script_lines = []
            for idx, script in enumerate(selected_scripts, 1):
                script_name = script.get('name', '')
                script_lines.append(f"{idx}. {script_name}")
            scripts_text = '\n'.join(script_lines)
        
        # 保存到数据库
        conn = get_db_connection()
        c = conn.cursor()
        try:
            # 插入进程数据
            current_time = time.strftime('%Y-%m-%d %H:%M:%S')
            c.execute('''
                INSERT INTO processes 
                (id, name, client, apple_id_filename, apple_id_count, status, scripts, create_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (process_id, process_name, process_client, apple_id_filename, apple_id_count, '已停止', scripts_text, current_time))
            conn.commit()
            logger.info(f"进程数据保存到数据库成功 - ID: {process_id}")
        except sqlite3.Error as e:
            logger.error(f"数据库插入错误: {str(e)}")
            conn.rollback()
            raise
        finally:
            conn.close()
        
        # 创建进程对象
        new_process = {
            "id": process_id,
            "name": process_name,
            "client": process_client,
            "apple_id": apple_id_filename,
            "apple_id_count": apple_id_count,
            "file_count": apple_id_count,
            "file_name": file_name,
            "status": "已停止",
            "scripts": selected_scripts,
            "create_time": current_time
        }
        
        # 创建进程logs目录下的appleid子目录
        process_log_dir = os.path.join(LOG_DIR, process_id)
        appleid_log_dir = os.path.join(process_log_dir, 'appleid')
        try:
            os.makedirs(appleid_log_dir, exist_ok=True)
            logger.info(f"成功创建进程appleid日志目录: {appleid_log_dir}")
        except Exception as e:
            logger.error(f"创建进程appleid日志目录失败: {str(e)}")
        
        # 添加到内存中的进程列表
        processes.append(new_process)
        logger.info(f"进程添加成功，当前进程总数: {len(processes)}")
        
        # 传输Apple ID文件到客户端
        logger.info(f"开始传输Apple ID文件到客户端 {process_client}")
        try:
            # 检查文件是否存在
            if os.path.exists(file_path):
                # 读取Apple ID文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    apple_id_text = f.read()
                
                logger.info(f"成功读取Apple ID文件 {apple_id_filename}，内容长度: {len(apple_id_text)} 字符")
                
                # 调用transfer_appleid_file函数传输文件内容
                transfer_success = transfer_appleid_file(process_client, apple_id_text)
                
                if transfer_success:
                    logger.info(f"Apple ID文件 {apple_id_filename} 成功传输到客户端 {process_client}")
                else:
                    logger.warning(f"Apple ID文件 {apple_id_filename} 传输到客户端 {process_client} 失败")
            else:
                logger.error(f"Apple ID文件不存在，无法传输: {file_path}")
        except Exception as e:
            logger.error(f"传输Apple ID文件时出错: {str(e)}")
        
        return jsonify({
            "success": True,
            "message": "进程添加成功",
            "data": {"process_id": process_id}
        })
    except Exception as e:
        logger.error(f"添加进程异常: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"添加进程失败: {str(e)}"
        })

@icloud_process_bp.route('/api/icloud/process/start', methods=['POST'])
def start_process():
    logger.debug(f'[DEBUG] 收到启动进程请求')
    try:
        process_id = request.json.get('process_id')
        logger.debug(f'[DEBUG] 请求启动进程ID: {process_id}')
        
        # 首先从数据库获取最新的进程状态，确保数据一致性
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT status, client FROM processes WHERE id = ?', (process_id,))
        db_result = c.fetchone()
        conn.close()
        
        if not db_result:
            logger.error(f'[ERROR] 数据库中找不到指定进程 - 进程ID: {process_id}')
            return jsonify({
                "success": False,
                "message": "找不到指定进程"
            })
        
        db_status, vm_ip = db_result[0], db_result[1]
        logger.debug(f'[DEBUG] 数据库中进程状态: {db_status}, VM IP: {vm_ip}')
        
        # 检查是否已在运行（内存中），并验证线程是否仍然活跃
        if process_id in running_tasks:
            thread = running_tasks[process_id]
            if thread.is_alive():
                logger.warning(f'[WARNING] 进程已在运行中 - 进程ID: {process_id}')
                return jsonify({
                    "success": False,
                    "message": "进程正在运行中"
                })
            else:
                # 线程已结束但仍在running_tasks中，清理旧线程
                logger.info(f'[INFO] 清理已结束的线程 - 进程ID: {process_id}')
                del running_tasks[process_id]
        
        # 幂等性检查：如果进程已经是启动中或执行中状态，直接返回成功
        if db_status in ['启动中', '执行中']:
            logger.info(f'[INFO] 进程已经处于运行相关状态，无需重复启动 - 进程ID: {process_id}, 当前状态: {db_status}')
            return jsonify({
                "success": True,
                "message": f"进程已经处于{db_status}状态"
            })
        
        # 查找内存中的进程引用
        process = None
        for p in processes:
            if p['id'] == process_id:
                process = p
                break
        
        if not process:
            # 如果内存中没有找到进程，创建一个基本进程对象
            process = {'id': process_id, 'status': db_status, 'client': vm_ip}
        
        logger.debug(f'[DEBUG] 找到进程 - 进程ID: {process_id}, 当前状态: {db_status}')
        logger.info(f'[INFO] 检查虚拟机连通性 - IP: {vm_ip}')
        
        # 检查虚拟机IP是否存活
        try:
            # 使用socket检查IP是否可达
            ping_success = False
            try:
                # 尝试连接到SSH端口
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    if s.connect_ex((vm_ip, 22)) == 0:
                        ping_success = True
                # 如果SSH端口不可达，尝试UDP
                if not ping_success:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                        s.settimeout(1)
                        try:
                            s.sendto(b'ping', (vm_ip, 80))
                            ping_success = True
                        except:
                            ping_success = False
            except:
                ping_success = False
            
            if not ping_success:
                logger.error(f'[ERROR] 虚拟机IP不可达 - {vm_ip}')
                # 更新状态为失败
                process['status'] = '失败'
                # 更新数据库状态
                update_process_status(process_id, '失败')
                # 写入日志
                write_log(process_id, f'进程启动失败: 虚拟机IP {vm_ip} 不可达')
                return jsonify({
                    "success": False,
                    "message": f"启动失败: 虚拟机IP {vm_ip} 不可达"
                })
            
            logger.info(f'[INFO] 虚拟机IP连通性检查通过')
        except Exception as e:
            logger.error(f'[ERROR] 检查虚拟机连通性时出错: {str(e)}')
            # 更新状态为失败
            process['status'] = '失败'
            # 更新数据库状态
            update_process_status(process_id, '失败')
            write_log(process_id, f'进程启动失败: 检查虚拟机连通性时出错 - {str(e)}')
            return jsonify({
                "success": False,
                "message": f"检查虚拟机连通性失败: {str(e)}"
            })
        
        # 清除可能存在的停止标志
        if process_id in stop_flags:
            del stop_flags[process_id]
            logger.debug(f'[DEBUG] 清除进程停止标志 - 进程ID: {process_id}')
        
        # 先更新数据库中的状态为启动中
        update_process_status(process_id, '启动中')
        # 然后更新内存中的状态
        process['status'] = '启动中'
        
        logger.debug(f'[DEBUG] 更新进程状态为启动中 - 进程ID: {process_id}')
        write_log(process_id, f'进程开始启动')
        
        # 创建独立线程执行进程，确保每个进程在独立线程中运行
        logger.debug(f'[DEBUG] 创建执行线程 - 进程ID: {process_id}')
        thread = threading.Thread(
            target=monitor_and_restart_process_after_reboot, 
            args=(vm_ip, process_id, False),
            daemon=True
        )
        # 立即保存到running_tasks字典
        running_tasks[process_id] = thread
        # 启动线程
        thread.start()
        
        logger.info(f'[INFO] 进程线程已创建并启动 - 进程ID: {process_id}, 线程ID: {thread.ident}')
        logger.debug(f'[DEBUG] 线程已启动，任务已添加到运行队列')
        
        return jsonify({
            "success": True,
            "message": "进程启动命令已发送，正在启动"
        })
        
    except Exception as e:
        logger.error(f'[ERROR] 启动进程异常: {str(e)}', exc_info=True)
        # 尝试更新状态为失败
        try:
            if 'process_id' in locals():
                update_process_status(process_id, '失败')
                write_log(process_id, f'进程启动异常: {str(e)}')
        except:
            pass
        
        return jsonify({
            "success": False,
            "message": f"启动进程失败: {str(e)}"
        })

@icloud_process_bp.route('/api/icloud/process/<process_id>', methods=['GET'])
def get_process_details(process_id):
    """获取单个进程的详细信息，用于前端异步轮询状态更新"""
   # logger.debug(f'[DEBUG] 请求获取进程详情 - 进程ID: {process_id}')
    
    try:
        # 从数据库获取进程的最新状态和信息
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            SELECT id, name, client, apple_id_filename, apple_id_count, status, create_time, scripts 
            FROM processes 
            WHERE id = ?
        ''', (process_id,))
        process_data = c.fetchone()
        conn.close()
        
        if not process_data:
            logger.error(f'[ERROR] 找不到指定进程 - 进程ID: {process_id}')
            return jsonify({
                "success": False,
                "message": "找不到指定进程"
            })
        
        # 构造进程信息字典
        process = {
            'id': process_data[0],
            'name': process_data[1],
            'client': process_data[2],
            'apple_id_filename': process_data[3],
            'apple_id_count': process_data[4],
            'status': process_data[5],
            'create_time': process_data[6],
            'scripts': process_data[7]
        }
        
        # 如果内存中有进程信息，可以合并最新状态
        for p in processes:
            if p['id'] == process_id:
                # 优先使用内存中的状态，因为可能更新更快
                process['status'] = p.get('status', process['status'])
                break
        
       # logger.debug(f'[DEBUG] 成功获取进程详情 - 进程ID: {process_id}, 状态: {process["status"]}')
        return jsonify({
            "success": True,
            "process": process
        })
        
    except Exception as e:
        logger.error(f'[ERROR] 获取进程详情异常: {str(e)}', exc_info=True)
        return jsonify({
            "success": False,
            "message": f"获取进程详情失败: {str(e)}"
        })

@icloud_process_bp.route('/api/icloud/process/stop', methods=['POST'])
def stop_process():
    logger.debug(f'[DEBUG] 收到停止进程请求')
    try:
        process_id = request.json.get('process_id')
        logger.debug(f'[DEBUG] 请求停止进程ID: {process_id}')
        
        # 首先从数据库获取最新的进程状态，确保数据一致性
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT status, client FROM processes WHERE id = ?', (process_id,))
        db_result = c.fetchone()
        conn.close()
        
        if not db_result:
            logger.error(f'[ERROR] 数据库中找不到指定进程 - 进程ID: {process_id}')
            return jsonify({
                "success": False,
                "message": "找不到指定进程"
            })
        
        db_status, vm_ip = db_result[0], db_result[1]
        logger.debug(f'[DEBUG] 数据库中进程状态: {db_status}, VM IP: {vm_ip}')
        
        # 查找内存中的进程引用
        process = None
        for p in processes:
            if p['id'] == process_id:
                process = p
                break
        
        if not process:
            # 如果内存中没有找到进程，创建一个基本进程对象
            process = {'id': process_id, 'status': db_status, 'client': vm_ip}
        
        # 幂等性检查：如果进程已经是停止状态，直接返回成功
        if db_status in ['已停止', '已完成', '失败']:
            logger.info(f'[INFO] 进程已经处于停止状态，无需重复停止 - 进程ID: {process_id}, 当前状态: {db_status}')
            return jsonify({
                "success": True,
                "message": f"进程已经处于停止状态: {db_status}"
            })
        
        logger.debug(f'[DEBUG] 开始停止进程 - 进程ID: {process_id}')
        
        # 进程停止前，同步远程的三个文件到本地logs进程目录appleid目录
        logger.info(f'[INFO] 进程停止前，同步远程的三个文件: icloud.txt, icloud2.txt, error.txt')
        write_log(process_id, '进程停止前，同步远程文件: icloud.txt, icloud2.txt, error.txt')
        
        # 同步文件函数
        def sync_remote_files_on_stop():
            """同步远端的三个文件到本地logs进程目录appleid目录"""
            appleid_log_dir = os.path.join(LOG_DIR, process_id, 'appleid')
            os.makedirs(appleid_log_dir, exist_ok=True)
            
            local_files = {
                'icloud.txt': os.path.join(appleid_log_dir, 'icloud.txt'),
                'icloud2.txt': os.path.join(appleid_log_dir, 'icloud2.txt'),
                'error.txt': os.path.join(appleid_log_dir, 'error.txt')
            }
            remote_files = {
                'icloud.txt': ICLOUD_TXT_PATH,
                'icloud2.txt': ICLOUD2_TXT_PATH,
                'error.txt': ERROR_TXT_PATH
            }
            
            sync_results = {}
            for file_name, remote_path in remote_files.items():
                try:
                    local_path = local_files[file_name]
                    if download_file_from_remote(vm_ip, remote_path, local_path):
                        logger.info(f'[INFO] 成功同步文件: {file_name} 到 {local_path}')
                        sync_results[file_name] = 'success'
                    else:
                        logger.warning(f'[WARNING] 同步文件: {file_name} 失败')
                        sync_results[file_name] = 'failed'
                except Exception as e:
                    logger.error(f'[ERROR] 同步文件 {file_name} 时发生异常: {str(e)}')
                    sync_results[file_name] = f'error: {str(e)}'
            
            return sync_results
        
        # 执行文件同步
        try:
            sync_results = sync_remote_files_on_stop()
            write_log(process_id, f'文件同步结果: {json.dumps(sync_results)}')
        except Exception as sync_error:
            logger.error(f'[ERROR] 同步文件时发生异常: {str(sync_error)}')
            write_log(process_id, f'文件同步异常: {str(sync_error)}')
        
        # 尝试从远程下载最新的icloud.txt文件（如果进程正在执行中）
        if db_status == '执行中' or process.get('status') == '执行中':
            logger.info(f'[INFO] 进程停止前，从远程下载最新的icloud.txt - VM IP: {vm_ip}')
            write_log(process_id, '进程停止前，从远程下载最新的icloud.txt...')
            
            # 从远程下载icloud.txt到本地临时文件（使用单独的try-except，确保不影响主流程）
            try:
                download_file_from_remote(vm_ip, ICLOUD_TXT_PATH, TEMP_PLIST_PATH)
            except Exception as download_error:
                logger.error(f'[ERROR] 下载icloud.txt文件失败: {str(download_error)}')
        
        # 设置停止标志，通知进程线程自行终止
        stop_flags[process_id] = True
        logger.info(f'[INFO] 设置进程停止标志 - 进程ID: {process_id}')
        
        # 更新状态为已停止（先更新数据库，确保持久化）
        update_process_status(process_id, '已停止')
        
        # 更新内存中的进程状态
        process['status'] = '已停止'
        logger.debug(f'[DEBUG] 更新进程状态为已停止 - 进程ID: {process_id}')
        write_log(process_id, '进程被手动停止')
        
        # 从运行任务中移除（如果存在）
        if process_id in running_tasks:
            logger.debug(f'[DEBUG] 从运行任务中移除进程 - 进程ID: {process_id}')
            del running_tasks[process_id]
        
        # 创建一个单独的线程来执行SSH操作，避免阻塞响应
        def execute_ssh_stop_script():
            try:
                logger.info(f'[INFO] 尝试通过SSH停止远端app客户端 - IP: {vm_ip}')
                # 导入配置获取脚本目录和密码
                import os
                from config import macos_script_dir, restart_scptRunner, vm_password
                
                # 获取脚本文件名
                script_filename = 'stop_scptapp.scpt'
                
                # 构建本地脚本完整路径
                local_script_path = os.path.join(macos_script_dir, script_filename)
                logger.debug(f'[DEBUG] 本地脚本路径: {local_script_path}')
                
                # 在虚拟机上的脚本路径，使用config.py中的restart_scptRunner配置
                vm_script_path = f'{restart_scptRunner}{script_filename}'
                logger.debug(f'[DEBUG] 虚拟机脚本路径: {vm_script_path}')
                
                # 尝试连接SSH并执行脚本，添加密码参数以确保认证成功
                with SSHClient(hostname=vm_ip, username=vm_username, password=vm_password, timeout=5) as ssh_client:
                    # 检查虚拟机上是否存在脚本文件
                    check_cmd = f'test -f {vm_script_path} && echo "exists" || echo "not exists"'
                    success_check, output_check, _, _ = ssh_client.execute_command(check_cmd, timeout=10)
                    
                    # 确保脚本可用（存在或上传）
                    script_available = False
                    if success_check and "exists" in output_check:
                        script_available = True
                    elif os.path.exists(local_script_path):
                        logger.info(f'[INFO] 尝试上传脚本到虚拟机 - {vm_script_path}')
                        upload_success = ssh_client.upload_file(local_script_path, vm_script_path)
                        if upload_success:
                            logger.info(f'[INFO] 脚本上传成功')
                            script_available = True
                        else:
                            logger.error(f'[ERROR] 脚本上传失败 - 无法复制到虚拟机')
                    else:
                        logger.error(f'[ERROR] 本地脚本文件不存在: {local_script_path}')
                    
                    # 如果脚本可用，循环尝试执行直到成功或达到最大次数
                    if script_available:
                        cmd = f'osascript {vm_script_path}'
                        max_attempts = 3
                        attempt = 0
                        stop_success = False
                        
                        while attempt < max_attempts and not stop_success:
                            attempt += 1
                            logger.info(f'[INFO] 执行stop_scptapp.scpt (尝试 {attempt}/{max_attempts})')
                            success, output, error, exit_code = ssh_client.execute_command(cmd, timeout=30)
                            
                            # 即使exit_code不为0，也检查输出是否包含'Success'或'所有运行中的应用已处理完成'来判断实际是否成功
                            output_str = output.strip() if output else ''
                            if success and (exit_code == 0 or 'Success' in output_str or '所有运行中的应用已处理完成' in output_str):
                                logger.info(f'[INFO] 成功调用stop_scptapp.scpt停止远端app客户端 - IP: {vm_ip}')
                                stop_success = True
                                
                                # 验证是否真正停止了进程
                                ps_cmd = "ps aux | grep scpt | grep -v grep"
                                check_success, check_output, _, _ = ssh_client.execute_command(ps_cmd, timeout=10)
                                if check_success and check_output.strip():
                                    logger.warning(f'[WARNING] 执行stop_scptapp.scpt后仍然存在scpt进程')
                                else:
                                    logger.info(f'[INFO] 确认scpt进程已停止')
                            else:
                                logger.warning(f'[WARNING] 调用stop_scptapp.scpt失败 (尝试 {attempt}/{max_attempts}) - 退出码: {exit_code}, 错误: {error}')
                                if attempt < max_attempts:
                                    logger.info(f'[INFO] 等待3秒后重试')
                                    time.sleep(3)
                                else:
                                    logger.error(f'[ERROR] 达到最大尝试次数，停止进程失败')
            except Exception as e:
                logger.error(f'[ERROR] 尝试停止远端app客户端时发生异常: {str(e)}', exc_info=True)
        
        # 启动SSH操作线程
        ssh_thread = threading.Thread(target=execute_ssh_stop_script)
        ssh_thread.daemon = True
        ssh_thread.start()
        
        # 立即返回成功响应，不等待SSH操作完成
        return jsonify({
            "success": True,
            "message": "进程停止命令已发送，正在终止执行"
        })
        
    except Exception as e:
        logger.error(f'[ERROR] 停止进程异常: {str(e)}', exc_info=True)
        return jsonify({
            "success": False,
            "message": f"停止进程失败: {str(e)}"
        })

@icloud_process_bp.route('/api/icloud/process/detail/<process_id>')
def get_process_detail(process_id):
    logger.info(f'[INFO] 收到获取进程详情请求 - 进程ID: {process_id}')
    logger.debug(f'[DEBUG] 进程列表长度: {len(processes)}')
    try:
        # 先打印所有进程的ID，方便调试
        logger.debug(f'[DEBUG] 当前进程列表: {[p["id"] for p in processes]}')
        
        for process in processes:
            if process['id'] == process_id:
                logger.info(f'[INFO] 找到匹配的进程 - 进程ID: {process_id}, 进程名称: {process["name"]}, 状态: {process["status"]}')
                
                # 重新获取并统计文件中的实际有效Apple ID数量
                apple_id_text = process.get('apple_id')
                logger.debug(f'[DEBUG] 进程Apple ID文本存在: {bool(apple_id_text)}')
                if apple_id_text:
                    logger.debug(f'[DEBUG] 开始重新统计Apple ID数量 - 进程ID: {process_id}')
                    
                    # 使用辅助函数计算有效Apple ID数量
                    logger.info(f'[INFO] 开始重新统计Apple ID数量 - 进程ID: {process_id}')
                    apple_id_count, file_name = count_valid_apple_ids(apple_id_text)
                    logger.info(f'[INFO] 统计完成 - 有效行数: {apple_id_count}, 文件名: {file_name}')
                    
                    # 特殊处理icloud测试.txt文件
                    if file_name and 'icloud测试.txt' in file_name:
                        logger.info(f'[INFO] 检测到icloud测试.txt文件，执行特殊处理 - 进程ID: {process_id}')
                        
                        # 重新获取原始行数据进行更详细的分析
                        apple_ids = apple_id_text.strip().split('\n')
                        logger.info(f'[INFO] 原始文本内容行分析 - 总行数: {len(apple_ids)}, 有效行: {apple_id_count}')
                        
                        # 逐行打印内容进行调试
                        for idx, line in enumerate(apple_ids, 1):
                            line_stripped = line.strip()
                            parts = line_stripped.split('----')
                            logger.info(f'[INFO] 行 {idx}: "{line_stripped}", 非空: {bool(line_stripped)}, 部分数量: {len(parts)}')
                    
                    # 更新进程对象中的数量字段
                    process['apple_id_count'] = apple_id_count
                    process['file_count'] = apple_id_count  # 兼容前端使用的两个字段
                    process['file_name'] = file_name  # 确保file_name字段存在
                    
                    logger.info(f'[INFO] Apple ID数量统计完成并更新 - 进程ID: {process_id}, 有效数量: {apple_id_count}, 文件名: {file_name}')
                else:
                    logger.debug(f'[DEBUG] 进程没有Apple ID数据 - 进程ID: {process_id}')
                    # 确保字段存在，设置为0
                    process['apple_id_count'] = 0
                    process['file_count'] = 0
                    process['file_name'] = None  # 确保file_name字段存在
                
                result_data = {
                    "success": True,
                    "data": process
                }
                logger.info(f'[INFO] 返回进程详情响应 - 进程ID: {process_id}, 响应数据: {json.dumps({"success": result_data["success"], "data": {"id": process["id"], "name": process["name"], "apple_id_count": process.get("apple_id_count"), "file_count": process.get("file_count"), "file_name": process.get("file_name"), "status": process["status"]}})}')
                return jsonify(result_data)
        
        logger.error(f'[ERROR] 找不到指定进程 - 进程ID: {process_id}, 请检查进程ID是否正确')
        return jsonify({
            "success": False,
            "message": f"找不到指定进程，进程ID: {process_id}"
        })
    except Exception as e:
        logger.error(f'[ERROR] 获取进程详情异常: {str(e)}')
        return jsonify({
            "success": False,
            "message": f"获取进程详情失败: {str(e)}"
        })


@icloud_process_bp.route('/api/icloud/process/delete', methods=['POST'])
def delete_process():
    # 记录API调用开始
    logger.info("===== DELETE PROCESS API CALL START =====")
    logger.info(f"时间: {datetime.now()}")
    logger.info(f"请求方法: {request.method}")
    logger.info(f"请求路径: {request.path}")
    logger.info(f"客户端IP: {request.remote_addr}")
    
    # 获取请求数据
    data = request.json
    logger.info(f"请求数据: {data}")
    
    # 获取要删除的进程ID
    process_id = data.get('process_id') if data else None
    logger.info(f"提取的进程ID: {process_id}")
    
    # 验证参数
    if not process_id:
        error_msg = "进程ID不能为空"
        logger.error(f"❌ 验证失败: {error_msg}")
        logger.info("===== DELETE PROCESS API CALL END (FAILED - MISSING PARAM) =====")
        return jsonify({
            'success': False,
            'message': error_msg
        })
    
    logger.info("✅ 参数验证通过，开始数据库操作")
    
    # 数据库删除操作
    conn = None
    try:
        # 检查进程是否正在运行
        if process_id in running_tasks:
            logger.warning(f"❌ 进程正在运行中，无法删除 - 进程ID: {process_id}")
            return jsonify({
                "success": False,
                "message": "进程正在运行中，无法删除"
            })
        
        # 获取数据库连接
        logger.info("正在获取数据库连接...")
        conn = get_db_connection()
        c = conn.cursor()
        logger.info("✅ 数据库连接获取成功")
        
        # 先查询要删除的进程是否存在
        logger.info(f"查询进程信息: SELECT name, status FROM processes WHERE id = '{process_id}'")
        c.execute('SELECT name, status FROM processes WHERE id = ?', (process_id,))
        db_process = c.fetchone()
        logger.info(f"查询结果: {db_process}")
        
        # 执行删除操作
        logger.info(f"执行删除操作: DELETE FROM processes WHERE id = '{process_id}'")
        c.execute('DELETE FROM processes WHERE id = ?', (process_id,))
        affected_rows = c.rowcount
        conn.commit()
        logger.info(f"✅ 删除操作完成，影响行数: {affected_rows}")
        conn.close()
        
        # 验证删除结果
        logger.info("验证删除结果...")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT count(*) FROM processes WHERE id = ?', (process_id,))
        remaining_count = c.fetchone()[0]
        conn.close()
        
        db_deleted = remaining_count == 0
        logger.info(f"验证结果: {'成功删除' if db_deleted else '仍然存在'}")
        
        # 从内存中删除进程
        process_exists = False
        for i, process in enumerate(processes):
            if process['id'] == process_id:
                process_exists = True
                logger.info(f"从内存中删除进程: {process['name']}")
                processes.pop(i)
                break
        
        # 清理进程输出日志
        if process_id in process_output_logs:
            logger.info(f"清理进程输出日志")
            del process_output_logs[process_id]
        
        # 删除相关日志文件
        process_log_dir = os.path.join(LOG_DIR, process_id)
        if os.path.exists(process_log_dir):
            logger.info(f"删除进程日志目录: {process_log_dir}")
            shutil.rmtree(process_log_dir)
            logger.info(f"进程日志目录已删除")
        
        if db_deleted:
            success_msg = f"进程ID {process_id} 删除成功"
            logger.info(f"✅ 操作成功: {success_msg}")
            logger.info("===== DELETE PROCESS API CALL END (SUCCESS) =====")
            
            return jsonify({
                'success': True,
                'message': success_msg,
                'deleted_id': process_id,
                'affected_rows': affected_rows,
                'remaining_count': remaining_count
            })
        else:
            error_msg = f"进程不存在或已被删除"
            logger.error(f"❌ 删除失败: {error_msg}")
            logger.info("===== DELETE PROCESS API CALL END (FAILED - NOT FOUND) =====")
            
            return jsonify({
                'success': False,
                'message': error_msg,
                'process_id': process_id
            })
    
    except Exception as e:
        # 发生错误时回滚
        if conn:
            logger.error(f"❌ 发生异常，执行回滚操作: {str(e)}")
            conn.rollback()
        
        error_msg = f"删除进程时发生错误: {str(e)}"
        logger.error(f"❌ 异常详情: {error_msg}")
        logger.error(f"异常类型: {type(e).__name__}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        logger.info("===== DELETE PROCESS API CALL END (FAILED - EXCEPTION) =====")
        
        # 在异常情况下也尝试清理内存
        if process_id:
            for i, process in enumerate(processes):
                if process['id'] == process_id:
                    logger.info(f"异常情况下从内存中清理进程: {process_id}")
                    processes.pop(i)
                    break
        
        return jsonify({
            'success': False,
            'message': error_msg,
            'error_type': type(e).__name__
        })
    finally:
        # 确保关闭连接
        if conn:
            logger.info("关闭数据库连接")
            conn.close()

# 添加兼容旧版API的路由
@icloud_process_bp.route('/api/icloud/process/output/<process_id>')
def get_process_output(process_id):
    try:
        # 检查进程是否存在
        process_exists = False
        for process in processes:
            if process['id'] == process_id:
                process_exists = True
                process_info = process
                break
        
        if not process_exists:
            return jsonify({'success': False, 'message': '进程不存在'})
        
        # 获取进程输出，如果不存在则返回模拟输出
        if process_id not in process_output_logs:
            # 为旧进程生成模拟输出
            output = f"[{time.strftime('%H:%M:%S')}] 进程 {process_info['name']} 输出日志\n"
            output += f"[{time.strftime('%H:%M:%S')}] 客户端: {process_info['client']}\n"
            output += f"[{time.strftime('%H:%M:%S')}] Apple ID: {process_info['apple_id']}\n"
            output += f"[{time.strftime('%H:%M:%S')}] 状态: {process_info['status']}\n"
            
            if process_info['status'] == '执行中':
                output += f"[{time.strftime('%H:%M:%S')}] 正在执行操作...\n"
                output += f"[{time.strftime('%H:%M:%S')}] 处理进度: 50%\n"
            elif process_info['status'] == '已停止':
                output += f"[{time.strftime('%H:%M:%S')}] 进程已停止\n"
            elif process_info['status'] == '已完成':
                output += f"[{time.strftime('%H:%M:%S')}] 进程执行完成\n"
                output += f"[{time.strftime('%H:%M:%S')}] 结果: 成功\n"
            elif process_info['status'] == '失败':
                output += f"[{time.strftime('%H:%M:%S')}] 执行过程中出现错误\n"
            
            return jsonify({'success': True, 'output': output})
        
        # 如果进程正在运行，添加一些动态输出
        if process_info['status'] == '执行中':
            # 添加一些模拟的进度更新
            import random
            progress = random.randint(0, 100)
            actions = ['正在连接客户端...', '正在验证账号...', '正在执行操作...', '正在同步数据...', '处理中...']
            random_action = random.choice(actions)
            process_output_logs[process_id] += f"[{time.strftime('%H:%M:%S')}] {random_action} - 进度: {progress}%\n"
        
        return jsonify({'success': True, 'output': process_output_logs[process_id]})
    except Exception as e:
        logger.error(f"获取进程输出失败: {str(e)}")
        return jsonify({'success': False, 'message': f'获取进程输出失败: {str(e)}', 'output': f'错误: {str(e)}'})

# 初始化时从数据库同步进程列表
sync_process_list_from_db()

@icloud_process_bp.route('/api/icloud/process/logs/<process_id>')
def get_process_logs(process_id):
    logger.debug(f'[DEBUG] 收到获取进程日志请求 - 进程ID: {process_id}')
    try:
        process_log_dir = os.path.join(LOG_DIR, process_id)
        logger.debug(f'[DEBUG] 进程日志目录: {process_log_dir}')
        
        if not os.path.exists(process_log_dir):
            logger.warning(f'[WARNING] 进程日志目录不存在 - 进程ID: {process_id}')
            return jsonify({
                "success": False,
                "message": "暂无日志"
            })
        
        logger.debug(f'[DEBUG] 进程日志目录存在，开始查找日志文件')
        # 获取最新的日志文件
        log_files = sorted([f for f in os.listdir(process_log_dir) if f.endswith('.log')], reverse=True)
        logger.debug(f'[DEBUG] 找到 {len(log_files)} 个日志文件')
        
        if not log_files:
            logger.warning(f'[WARNING] 进程日志目录中无日志文件 - 进程ID: {process_id}')
            return jsonify({
                "success": False,
                "message": "暂无日志"
            })
        
        latest_log_file = log_files[0]
        logger.debug(f'[DEBUG] 选择最新日志文件: {latest_log_file}')
        
        # 读取日志内容
        log_file_path = os.path.join(process_log_dir, latest_log_file)
        logger.debug(f'[DEBUG] 读取日志文件: {log_file_path}')
        
        try:
            start_time = time.time()
            with open(log_file_path, 'r', encoding='utf-8') as f:
                logs = f.readlines()
            elapsed_time = time.time() - start_time
            logger.debug(f'[DEBUG] 日志文件读取完成，共 {len(logs)} 行，耗时: {elapsed_time:.2f}秒')
            
            return jsonify({
                "success": True,
                "data": {
                    "logs": logs,
                    "file_name": latest_log_file
                }
            })
        except UnicodeDecodeError as e:
            logger.error(f'[ERROR] 日志文件编码错误: {str(e)}')
            return jsonify({
                "success": False,
                "message": f"日志文件编码错误: {str(e)}"
            })
        except Exception as e:
            logger.error(f'[ERROR] 读取日志文件异常: {str(e)}')
            return jsonify({
                "success": False,
                "message": f"读取日志失败: {str(e)}"
            })
    except Exception as e:
        logger.error(f'[ERROR] 获取进程日志异常: {str(e)}')
        return jsonify({
            "success": False,
            "message": f"获取日志失败: {str(e)}"
        })