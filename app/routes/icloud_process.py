from flask import Blueprint, jsonify, request
from datetime import datetime
import os
import json
import requests
import subprocess
import time
import threading
import shutil
import logging
# 导入配置模块，使用appleid_unused_dir路径
from config import appleid_unused_dir

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('icloud_process')

# 创建蓝图
icloud_process_bp = Blueprint('icloud_process', __name__)

# 配置项
SCRIPT_DIR = '/Users/wx/Documents/macos_script/macos_scpt/macos11/'
SCPTRUNNER_PORT = 8787
ICLOUD_TXT_PATH = '/Users/wx/Desktop/icloud.txt'
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'logs'))

# 确保日志目录存在
os.makedirs(LOG_DIR, exist_ok=True)

# 进程列表数据存储
processes = []

# 正在运行的进程任务
running_tasks = {}

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
        logger.debug(f'[DEBUG] 辅助函数 - 无Apple ID文本，返回0')
        return 0, file_name
    
    # 分割文本并统计有效行
    apple_ids = apple_id_text.strip().split('\n')
    valid_apple_ids = []
    
    for idx, line in enumerate(apple_ids, 1):
        line_stripped = line.strip()
        if line_stripped:
            parts = line_stripped.split('----')
            logger.debug(f'[DEBUG] 辅助函数 - 行 {idx} 分割后部分数量: {len(parts)}, 内容: {line_stripped[:50]}...')
            if len(parts) >= 4:
                valid_apple_ids.append(line_stripped)
                logger.debug(f'[DEBUG] 辅助函数 - 行 {idx} 有效，添加到计数中')
            else:
                logger.debug(f'[DEBUG] 辅助函数 - 行 {idx} 无效，部分数量不足4个')
        else:
            logger.debug(f'[DEBUG] 辅助函数 - 行 {idx} 为空行，跳过')
    
    apple_id_count = len(valid_apple_ids)
    logger.debug(f'[DEBUG] 辅助函数 - 统计完成 - 有效行数: {apple_id_count}, 总行数: {len(apple_ids)}, 文件名: {file_name}')
    return apple_id_count, file_name

# 辅助函数：写入日志
def write_log(process_id, message):
    process_log_dir = os.path.join(LOG_DIR, process_id)
    logger.debug(f'[DEBUG] 准备写入日志 - 进程ID: {process_id}, 日志目录: {process_log_dir}')
    os.makedirs(process_log_dir, exist_ok=True)
    log_file = os.path.join(process_log_dir, f'{datetime.now().strftime("%Y%m%d")}.log')
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            log_entry = f'[{timestamp}] {message}\n'
            f.write(log_entry)
        logger.debug(f'[DEBUG] 日志写入成功 - 进程ID: {process_id}, 文件: {log_file}')
    except Exception as e:
        logger.error(f'[ERROR] 日志写入失败: {str(e)}')

# 辅助函数：执行scpt脚本
def run_scpt_script(vm_ip, script_name):
    logger.debug(f'[DEBUG] 准备执行脚本 - VM IP: {vm_ip}, 脚本名称: {script_name}')
    url = f'http://{vm_ip}:{SCPTRUNNER_PORT}/run?path={SCRIPT_DIR}{script_name}'
    logger.debug(f'[DEBUG] 请求URL: {url}')
    try:
        start_time = time.time()
        response = requests.get(url, timeout=300)  # 5分钟超时
        elapsed_time = time.time() - start_time
        logger.debug(f'[DEBUG] 脚本执行完成 - 响应状态码: {response.status_code}, 耗时: {elapsed_time:.2f}秒')
        response.raise_for_status()
        result = response.json()
        logger.debug(f'[DEBUG] 脚本执行结果: {json.dumps(result)}')
        return result
    except requests.exceptions.Timeout:
        logger.error(f'[ERROR] 脚本执行超时: {vm_ip} - {script_name}')
        return {'result': '脚本执行超时'}
    except requests.exceptions.ConnectionError:
        logger.error(f'[ERROR] 连接失败: {vm_ip}:{SCPTRUNNER_PORT}')
        return {'result': f'连接失败: {vm_ip}:{SCPTRUNNER_PORT}'}
    except Exception as e:
        logger.error(f'[ERROR] 脚本执行异常: {str(e)}')
        return {'result': f'脚本执行失败: {str(e)}'}

# 辅助函数：传输appleid文本文件
def transfer_appleid_file(vm_ip, apple_id_text):
    logger.debug(f'[DEBUG] 准备传输Apple ID文件 - VM IP: {vm_ip}, 目标路径: {ICLOUD_TXT_PATH}')
    try:
        # 创建临时文件
        temp_file = os.path.join(os.environ.get('TEMP', '/tmp'), 'icloud.txt')
        logger.debug(f'[DEBUG] 创建临时文件: {temp_file}')
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(apple_id_text)
        logger.debug(f'[DEBUG] 临时文件创建成功，内容长度: {len(apple_id_text)} 字符')
        
        # 使用scp传输文件
        scp_command = f'scp {temp_file} wx@{vm_ip}:{ICLOUD_TXT_PATH}'
        logger.debug(f'[DEBUG] 执行SCP命令: {scp_command}')
        start_time = time.time()
        result = subprocess.run(scp_command, shell=True, capture_output=True, text=True)
        elapsed_time = time.time() - start_time
        logger.debug(f'[DEBUG] SCP命令执行完成，返回码: {result.returncode}, 耗时: {elapsed_time:.2f}秒')
        
        # 记录SCP输出
        if result.stdout:
            logger.debug(f'[DEBUG] SCP标准输出: {result.stdout.strip()}')
        if result.stderr:
            logger.debug(f'[DEBUG] SCP标准错误: {result.stderr.strip()}')
        
        # 删除临时文件
        if os.path.exists(temp_file):
            os.remove(temp_file)
            logger.debug(f'[DEBUG] 临时文件已删除: {temp_file}')
        
        success = result.returncode == 0
        logger.debug(f'[DEBUG] 文件传输结果: {"成功" if success else "失败"}')
        return success
    except Exception as e:
        logger.error(f'[ERROR] 文件传输异常: {str(e)}')
        return False

# 辅助函数：等待虚拟机启动完成
def wait_for_vm_ready(vm_ip, timeout=300):
    logger.debug(f'[DEBUG] 等待虚拟机启动 - IP: {vm_ip}, 超时时间: {timeout}秒')
    start_time = time.time()
    attempt = 0
    
    while time.time() - start_time < timeout:
        attempt += 1
        elapsed = time.time() - start_time
        logger.debug(f'[DEBUG] 尝试 #{attempt} - 已等待: {elapsed:.1f}秒')
        
        try:
            # 检查IP是否存活
            logger.debug(f'[DEBUG] 检查IP是否存活: {vm_ip}')
            response = subprocess.run(['ping', '-n', '1', '-w', '1', vm_ip], 
                                     capture_output=True, text=True)
            
            if response.returncode != 0:
                logger.debug(f'[DEBUG] IP {vm_ip} 未响应')
                time.sleep(5)
                continue
            
            logger.debug(f'[DEBUG] IP {vm_ip} 已响应，继续检查端口')
            
            # 检查scptrunner端口是否开放
            logger.debug(f'[DEBUG] 检查端口 {SCPTRUNNER_PORT} 是否开放')
            response = subprocess.run(['telnet', vm_ip, str(SCPTRUNNER_PORT)], 
                                     capture_output=True, text=True, timeout=2)
            
            if 'Connected' in response.stdout:
                logger.debug(f'[DEBUG] 端口连接成功，虚拟机已准备就绪')
                return True
            else:
                logger.debug(f'[DEBUG] 端口未开放，继续等待')
        except Exception as e:
            logger.error(f'[ERROR] 检查虚拟机状态时发生异常: {str(e)}')
        
        time.sleep(5)
    
    logger.warning(f'[WARNING] 虚拟机启动超时 - IP: {vm_ip}, 等待时间: {timeout}秒')
    return False

# 辅助函数：执行五码更换
def change_wuma(vm_ip, wuma_config):
    logger.debug(f'[DEBUG] 准备更换五码 - VM IP: {vm_ip}, 配置: {wuma_config}')
    try:
        # 这里应该调用批量更换五码的API
        # 由于没有具体实现，这里仅作为示例
        write_log('', f'更换五码: {vm_ip}, 配置: {wuma_config}')
        logger.debug(f'[DEBUG] 开始等待虚拟机重启')
        # 等待虚拟机重启
        result = wait_for_vm_ready(vm_ip)
        logger.debug(f'[DEBUG] 虚拟机重启完成 - 状态: {"成功" if result else "失败"}')
        return result
    except Exception as e:
        logger.error(f'[ERROR] 更换五码异常: {str(e)}')
        write_log('', f'更换五码失败: {str(e)}')
        return False

# 主进程执行函数
def execute_process(process_id):
    logger.debug(f'[DEBUG] 开始执行进程 - 进程ID: {process_id}')
    process = None
    for p in processes:
        if p['id'] == process_id:
            process = p
            break
    
    if not process:
        logger.error(f'[ERROR] 找不到指定进程 - 进程ID: {process_id}')
        return
    
    logger.debug(f'[DEBUG] 找到进程 - 进程名称: {process["name"]}, 客户端: {process["client"]}')
    
    try:
        # 更新状态为执行中
        process['status'] = '执行中'
        logger.debug(f'[DEBUG] 更新进程状态为执行中 - 进程ID: {process_id}')
        write_log(process_id, f'进程开始执行: {process["name"]}')
        
        # 获取虚拟机IP（这里假设client字段包含IP信息）
        vm_ip = process['client']  # 实际应用中可能需要从配置或数据库获取
        logger.debug(f'[DEBUG] 使用虚拟机IP: {vm_ip}')
        
        # 传输appleid文本文件
        logger.debug(f'[DEBUG] 准备传输Apple ID文件')
        if not transfer_appleid_file(vm_ip, process['apple_id']):
            logger.error(f'[ERROR] 传输Apple ID文件失败 - 进程ID: {process_id}')
            write_log(process_id, '传输Apple ID文件失败')
            process['status'] = '失败'
            return
        logger.debug(f'[DEBUG] Apple ID文件传输成功')
        
        # 读取appleid文本文件行数，排除空行
        apple_ids = process['apple_id'].strip().split('\n')
        # 过滤空行
        non_empty_apple_ids = [id.strip() for id in apple_ids if id.strip()]
        logger.debug(f'[DEBUG] 发现 {len(non_empty_apple_ids)} 个有效Apple ID（原始行数: {len(apple_ids)}）')
        
        for idx, apple_id in enumerate(non_empty_apple_ids, 1):
            logger.debug(f'[DEBUG] 开始处理Apple ID ({idx}/{len(non_empty_apple_ids)}): {apple_id}')
            write_log(process_id, f'开始处理Apple ID: {apple_id}')
            
            # 执行登录脚本
            logger.debug(f'[DEBUG] 执行登录脚本')
            login_result = run_scpt_script(vm_ip, 'appleid_login.scpt')
            write_log(process_id, f'登录结果: {json.dumps(login_result)}')
            
            # 检查登录结果
            login_message = login_result.get('result', '')
            logger.debug(f'[DEBUG] 登录消息: {login_message}')
            
            if login_message == '':
                # 需要重启登录
                logger.debug(f'[DEBUG] 登录消息为空，执行重启登录')
                restart_result = run_scpt_script(vm_ip, 'login_restart.scpt')
                write_log(process_id, f'重启登录结果: {json.dumps(restart_result)}')
                # 重新执行登录
                logger.debug(f'[DEBUG] 重新执行登录')
                login_result = run_scpt_script(vm_ip, 'appleid_login.scpt')
                write_log(process_id, f'重新登录结果: {json.dumps(login_result)}')
                login_message = login_result.get('result', '')
            
            if 'MOBILEME_CREATE_UNAVAILABLE_MAC' in login_message:
                # 需要更换五码
                logger.warning(f'[WARNING] 检测到需要更换五码 - Apple ID: {apple_id}')
                write_log(process_id, '检测到需要更换五码')
                if change_wuma(vm_ip, 'default_config'):
                    logger.debug(f'[DEBUG] 五码更换成功，重新登录')
                    write_log(process_id, '五码更换成功，重新登录')
                    # 重新执行登录
                    login_result = run_scpt_script(vm_ip, 'appleid_login.scpt')
                    write_log(process_id, f'五码更换后登录结果: {json.dumps(login_result)}')
                else:
                    logger.error(f'[ERROR] 五码更换失败 - 进程终止')
                    write_log(process_id, '五码更换失败')
                    process['status'] = '失败'
                    return
            
            # 执行查询脚本
            logger.debug(f'[DEBUG] 执行查询脚本')
            query_result = run_scpt_script(vm_ip, 'queryiCloudAccount.scpt')
            write_log(process_id, f'查询结果: {json.dumps(query_result)}')
            
            # 执行注销脚本
            logger.debug(f'[DEBUG] 执行注销脚本')
            logout_result = run_scpt_script(vm_ip, 'logout_icloud.scpt')
            write_log(process_id, f'注销结果: {json.dumps(logout_result)}')
            
            logger.debug(f'[DEBUG] Apple ID处理完成 ({idx}/{len(non_empty_apple_ids)}): {apple_id}')
        
        # 所有操作完成
        process['status'] = '已完成'
        logger.debug(f'[DEBUG] 进程执行完成 - 进程ID: {process_id}, 进程名称: {process["name"]}')
        write_log(process_id, '进程执行完成')
        
    except Exception as e:
        error_msg = f'进程执行异常: {str(e)}'
        logger.error(f'[ERROR] {error_msg} - 进程ID: {process_id}')
        write_log(process_id, error_msg)
        process['status'] = '失败'
    finally:
        # 从运行任务中移除
        if process_id in running_tasks:
            logger.debug(f'[DEBUG] 从运行任务中移除进程 - 进程ID: {process_id}')
            del running_tasks[process_id]

# 进程管理路由
@icloud_process_bp.route('/api/icloud/process/list')
def get_process_list():
    logger.debug(f'[DEBUG] 收到获取进程列表请求')
    logger.debug(f'[DEBUG] 当前进程总数: {len(processes)}')
    result = jsonify({
        "success": True,
        "data": processes
    })
    logger.debug(f'[DEBUG] 返回进程列表响应')
    return result

@icloud_process_bp.route('/api/icloud/process/add', methods=['POST'])
def add_process():
    logger.debug(f'[DEBUG] 收到添加进程请求')
    try:
        data = request.json
        logger.debug(f'[DEBUG] 请求数据: {json.dumps(data)}')
        
        apple_id_text = data.get('apple_id')
        
        # 使用辅助函数计算有效Apple ID数量
        apple_id_count, file_name = count_valid_apple_ids(apple_id_text)
        
        new_process = {
            "id": str(len(processes) + 1),
            "name": data.get('process_name'),
            "script": data.get('process_script', ''),
            "client": data.get('process_client'),
            "apple_id": apple_id_text,
            "apple_id_count": apple_id_count,
            "file_count": apple_id_count,  # 兼容前端使用的两个字段
            "file_name": file_name,
            "status": "已停止",
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        logger.debug(f'[DEBUG] 创建新进程 - ID: {new_process["id"]}, 名称: {new_process["name"]}')
        processes.append(new_process)
        logger.debug(f'[DEBUG] 进程添加成功，当前进程总数: {len(processes)}')
        
        result = jsonify({
            "success": True,
            "message": "进程添加成功",
            "data": new_process
        })
        logger.debug(f'[DEBUG] 返回添加进程成功响应')
        return result
    except Exception as e:
        logger.error(f'[ERROR] 添加进程异常: {str(e)}')
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
        
        for process in processes:
            if process['id'] == process_id:
                # 检查是否已在运行
                if process_id in running_tasks:
                    logger.warning(f'[WARNING] 进程已在运行中 - 进程ID: {process_id}')
                    return jsonify({
                        "success": False,
                        "message": "进程正在运行中"
                    })
                
                logger.debug(f'[DEBUG] 找到进程 - 进程名称: {process["name"]}, 当前状态: {process["status"]}')
                
                # 更新状态为启动中
                process['status'] = '启动中'
                logger.debug(f'[DEBUG] 更新进程状态为启动中 - 进程ID: {process_id}')
                
                # 创建线程执行进程
                logger.debug(f'[DEBUG] 创建执行线程 - 进程ID: {process_id}')
                thread = threading.Thread(target=execute_process, args=(process_id,))
                thread.daemon = True
                thread.start()
                running_tasks[process_id] = thread
                logger.debug(f'[DEBUG] 线程已启动，任务已添加到运行队列')
                
                return jsonify({
                    "success": True,
                    "message": "进程已启动"
                })
        
        logger.error(f'[ERROR] 找不到指定进程 - 进程ID: {process_id}')
        return jsonify({
            "success": False,
            "message": "找不到指定进程"
        })
    except Exception as e:
        logger.error(f'[ERROR] 启动进程异常: {str(e)}')
        return jsonify({
            "success": False,
            "message": f"启动进程失败: {str(e)}"
        })

@icloud_process_bp.route('/api/icloud/process/stop', methods=['POST'])
def stop_process():
    logger.debug(f'[DEBUG] 收到停止进程请求')
    try:
        process_id = request.json.get('process_id')
        logger.debug(f'[DEBUG] 请求停止进程ID: {process_id}')
        
        for process in processes:
            if process['id'] == process_id:
                logger.debug(f'[DEBUG] 找到进程 - 进程名称: {process["name"]}, 当前状态: {process["status"]}')
                
                # 这里可以添加停止线程的逻辑，但实际上很难安全停止线程
                # 这里只是更新状态
                process['status'] = '已停止'
                logger.debug(f'[DEBUG] 更新进程状态为已停止 - 进程ID: {process_id}')
                write_log(process_id, '进程被手动停止')
                
                # 从运行任务中移除（如果存在）
                if process_id in running_tasks:
                    logger.debug(f'[DEBUG] 从运行任务中移除进程 - 进程ID: {process_id}')
                    del running_tasks[process_id]
                
                return jsonify({
                    "success": True,
                    "message": "进程已停止"
                })
        
        logger.error(f'[ERROR] 找不到指定进程 - 进程ID: {process_id}')
        return jsonify({
            "success": False,
            "message": "找不到指定进程"
        })
    except Exception as e:
        logger.error(f'[ERROR] 停止进程异常: {str(e)}')
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
    logger.debug(f'[DEBUG] 收到删除进程请求')
    try:
        process_id = request.json.get('process_id')
        logger.debug(f'[DEBUG] 请求删除进程ID: {process_id}')
        
        for i, process in enumerate(processes):
            if process['id'] == process_id:
                logger.debug(f'[DEBUG] 找到进程 - 进程名称: {process["name"]}, 状态: {process["status"]}')
                
                # 检查是否正在运行
                if process_id in running_tasks:
                    logger.warning(f'[WARNING] 进程正在运行中，无法删除 - 进程ID: {process_id}')
                    return jsonify({
                        "success": False,
                        "message": "进程正在运行中，无法删除"
                    })
                
                # 删除进程
                logger.debug(f'[DEBUG] 准备从进程列表中移除 - 索引: {i}')
                processes.pop(i)
                logger.debug(f'[DEBUG] 进程已从内存中移除，当前进程总数: {len(processes)}')
                write_log(process_id, '进程被删除')
                
                # 可以选择删除相关日志文件
                process_log_dir = os.path.join(LOG_DIR, process_id)
                if os.path.exists(process_log_dir):
                    logger.debug(f'[DEBUG] 删除进程日志目录: {process_log_dir}')
                    shutil.rmtree(process_log_dir)
                    logger.debug(f'[DEBUG] 进程日志目录已删除')
                else:
                    logger.debug(f'[DEBUG] 进程日志目录不存在: {process_log_dir}')
                
                return jsonify({
                    "success": True,
                    "message": "进程删除成功"
                })
        
        logger.error(f'[ERROR] 找不到指定进程 - 进程ID: {process_id}')
        return jsonify({
            "success": False,
            "message": "找不到指定进程"
        })
    except Exception as e:
        logger.error(f'[ERROR] 删除进程异常: {str(e)}')
        return jsonify({
            "success": False,
            "message": f"删除进程失败: {str(e)}"
        })

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