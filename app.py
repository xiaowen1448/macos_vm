import json
import ipaddress
import atexit
import signal
import threading
import subprocess
import base64
import sys
import socket
import secrets
import shutil
import csv
import io
import os
import psutil
import time
import paramiko
import re
import requests
import threading
import json
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
from app.routes.dashboard import dashboard_bp

# 导入日志工具和全局logger
from app.utils.log_utils import logger, logging, setup_logger
from app.utils.vm_cache import vm_cache, VMStatusCache
from app.utils.im_utils import *



# 禁用paramiko的debug日志输出
logging.getLogger('paramiko').setLevel(logging.WARNING)
logging.getLogger('paramiko.transport').setLevel(logging.WARNING)

# 直接使用从log_utils导入的全局logger，不再重复初始化

app = Flask(__name__, template_folder='web/templates', static_folder='web/static', static_url_path='/static')

# 增加缓冲区大小以解决大型文件的ERR_CONTENT_LENGTH_MISMATCH问题
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # 禁用缓存
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# 注册新蓝图
app.register_blueprint(vm_clone_bp)
app.register_blueprint(vm_management_bp)
app.register_blueprint(vm_bp)
app.register_blueprint(im_manager_bp)
app.register_blueprint(vnc_manager_bp)
app.register_blueprint(dashboard_bp)
app.secret_key = secrets.token_hex(32)  # 生成随机session密钥
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)  # 设置session过期时间

# 初始化SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 设置Flask应用的日志级别
app.logger.setLevel(logging.DEBUG)

# 启动时清除所有session（只执行一次）
# 添加一个全局标志来确保只执行一次
if not hasattr(sys.modules[__name__], '_sessions_cleared'):
    clear_sessions_on_startup()
    sys.modules[__name__]._sessions_cleared = True

# 禁用Werkzeug的HTTP请求日志（静态文件请求日志）
logging.getLogger('werkzeug').setLevel(logging.ERROR)
# 禁用Flask内置的HTTP访问日志
app.logger.disabled = False
logging.getLogger('werkzeug').disabled = True

# 导入并初始化所有路由蓝图
from app.routes import init_app
init_app(app)


# 确保 web/templates/ 目录下有 login.html 和 dashboard.html 文件，否则会报错。
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            # 检查是否是AJAX请求
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get(
                    'Content-Type') == 'application/json':
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
                        'redirect': url_for('dashboard.dashboard')
                    })
                else:
                    return redirect(url_for('dashboard.dashboard'))
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



# 以下路由已移至app/routes/vm.py蓝图中
# /batch_im_status
# /vm_info



# 以下路由已移至app/routes/vm.py蓝图中
# /vm_script
# /test_mupan
# /encrypt_code
# /encrypt_wuma
# /encrypt_id


# 导入proxy_assign模块中的函数
from app.routes.proxy_assign import get_nodes, import_nodes, get_countries, get_nodes_by_country, batch_assign

# 注册代理IP相关的API端点
@app.route('/api/nodes', methods=['GET'])
@login_required
def api_nodes():
    """获取所有节点列表"""
    return get_nodes()

@app.route('/api/nodes/import', methods=['POST'])
@login_required
def api_nodes_import():
    """导入VPN配置节点"""
    return import_nodes()

@app.route('/api/get_countries')
@login_required
def api_get_countries():
    """获取所有可用的国家地区"""
    return get_countries()

@app.route('/api/get_nodes_by_country')
@login_required
def api_get_nodes_by_country():
    """根据国家获取节点列表"""
    return get_nodes_by_country()

@app.route('/api/test_node_delay/<int:node_id>')
@login_required
def api_test_node_delay(node_id):
    """测试单个节点的延迟"""
    from app.routes.proxy_assign import test_node_delay
    return test_node_delay(node_id)

@app.route('/api/batch_assign', methods=['POST'])
@login_required
def api_batch_assign():
    """批量分配代理"""
    return batch_assign()

# 以下路由已移至app/routes/vm.py蓝图中
# /proxy_assign
# /soft_version
# /soft_env
# /client_management
# /json_parser
# /phone_management


# 批量发信相关路由已移动到 app/routes/mass_messaging.py

# 批量发信模板相关路由已移动到 app/routes/mass_messaging.py

# 批量发信核心API和其他相关路由已移动到 app/routes/mass_messaging.py

# websockify进程管理 - 使用全局定义，避免重复定义



# 旧的VNC WebSocket代理代码（保留以防需要）
vnc_connections = {}


@app.route('/logout')
@login_required
def logout():
    """用户登出"""
    username = session.get('username', 'unknown')
    session.clear()
    logger.info(f"用户 {username} 已登出")
    return redirect(url_for('login'))



# 成品虚拟机API端点 - 使用通用函数




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



@app.route('/api/vm_chengpin_ip_status/<vm_name>')
@login_required
def api_vm_chengpin_ip_status(vm_name):
    """获取成品虚拟机IP状态"""
    return get_ip_status_generic(vm_name, '成品虚拟机', VM_DIRS['chengpin'])




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




@app.route('/api/vm_10_12_ip_status/<vm_name>')
@login_required
def api_vm_10_12_ip_status(vm_name):
    """获取10.12目录虚拟机IP状态"""
    return get_ip_status_generic(vm_name, '10.12目录', VM_DIRS['10_12'])




# 五码管理相关API路由
@app.route('/api/wuma_list')
@login_required
def api_wuma_list():
    """获取五码列表"""
    #  logger.info("收到获取五码列表请求")
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 5))
        config_name = request.args.get('config', 'config')  # 默认使用config.txt
        list_type = request.args.get('type', 'available')  # available 或 used

        #  logger.debug(f"请求参数 - page: {page}, page_size: {page_size}, config: {config_name}, type: {list_type}")

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
            #  logger.debug(f"配置文件存在，开始读取")
            with open(config_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # logger.debug(f"读取到 {len(lines)} 行数据")

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
                        #  logger.debug(f"解析第 {i} 行数据: {wuma_item}")
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

        #   logger.debug(f"分页信息 - 总数: {total_count}, 总页数: {total_pages}, 当前页: {page}, 起始索引: {start_index}, 结束索引: {end_index}")

        # 获取当前页的数据
        current_page_data = wuma_data[start_index:end_index]
        # logger.debug(f"当前页数据条数: {len(current_page_data)}")

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

        #  logger.info(f"成功返回五码列表 - 总数: {total_count}, 当前页: {page}/{total_pages}, 类型: {list_type}")

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
    # logger.info("收到获取配置文件列表请求")
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
                logger.warning(f"行索引 {row_index} 超出范围 (0-{len(lines) - 1})")
                return jsonify({
                    'success': False,
                    'message': f'行索引 {row_index} 超出范围 (0-{len(lines) - 1})'
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

        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')

        if result.returncode != 0:
            return jsonify({
                'success': False,
                'message': f'获取运行中虚拟机列表失败: {result.stderr}'
            })

        running_vms = result.stdout.strip().split('\n')[1:]  # 跳过标题行
        # logger.info(f"获取到运行中虚拟机: {running_vms}")

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


# Apple ID管理相关API
@app.route('/api/appleid_files')
@login_required
def api_appleid_files():
    """获取Apple ID文件列表"""
    # logger.info("收到获取Apple ID文件列表请求")
    try:
        files = []
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
                     #   logger.info(f"发现Apple ID文件: {filename}")
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
    # logger.info("收到获取Apple ID文件内容请求")
    try:
        filename = request.args.get('file')
        if not filename:
            return jsonify({
                'success': False,
                'message': '未指定文件名'
            })
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
               # logger.info(f"成功使用 {encoding} 编码读取文件 {filename}")
                break
            except UnicodeDecodeError:
              #  logger.warning(f"使用 {encoding} 编码读取文件 {filename} 失败，尝试下一种编码")
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
                    'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).strftime(
                        '%Y-%m-%d %H:%M:%S') if os.path.exists(file_path) else ''
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
            custom_filename = re.sub(r'[^\w\-_.]', '_', custom_filename)
            filename = f"{custom_filename}.txt"
        else:
            # 使用原文件名，但确保是.txt格式
            base_name = os.path.splitext(file.filename)[0]
            filename = f"{base_name}.txt"
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
    # logger.info("收到获取Apple ID列表请求")
    try:
        apple_ids = []
        id_dir = os.path.join(project_root, appleid_unused_dir)

        # 确保ID目录存在
        if not os.path.exists(id_dir):
            os.makedirs(id_dir, exist_ok=True)
        # logger.info("创建ID_unused目录")

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
                            # logger.info(f"成功使用 {encoding} 编码读取文件 {filename}")
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
                    #  logger.info(f"从文件 {filename} 中读取到 {len(lines)} 行，提取到 {len([l for l in lines if '----' in l])} 个Apple ID")

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

            #  logger.info(f"总共找到 {len(apple_id_list)} 个唯一的Apple ID")

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

        # logger.info(f"批量IM登录验证通过 - 运行中虚拟机: {running_vms}, Apple ID文件: {apple_id_file}")
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
                #  logger.info(f"成功使用 {encoding} 编码读取文件 {apple_id_file}")
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

        #  logger.info(f"从文件 {apple_id_file} 中提取到 {len(apple_ids)} 个Apple ID")

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

        # logger.info(f"每个虚拟机分配 {apple_ids_per_vm} 个Apple ID，共使用 {len(apple_ids_to_distribute)} 个")

        results = []
        results_lock = threading.Lock()  # 用于保护results列表的线程安全

        def process_vm_login(vm_name, vm_index, apple_id_data):
            """处理单个虚拟机的登录过程"""
            vm_result = {
                'vm_name': vm_name,
                'success': False,
                'message': '',
                'apple_id_count': 1,
                'apple_id_range': f"{vm_index + 1}",
                'script_executed': False,
                'script_message': ''
            }

            try:
                #  logger.info(f"[线程] 开始处理虚拟机 {vm_name} 的登录")

                # 获取虚拟机IP
                vm_ip = get_vm_ip(vm_name)
                if not vm_ip:
                    vm_result['message'] = '无法获取虚拟机IP地址'
                    return vm_result

                # 获取分配给当前虚拟机的Apple ID（每个虚拟机一个）
                vm_apple_ids = [apple_id_data]

                # logger.info(f"[线程] 虚拟机 {vm_name} 分配第 {vm_index+1} 个Apple ID: {vm_apple_ids[0]}")

                # 创建临时文件
                temp_file_name = f"{vm_name}_appleid.txt"
                temp_file_path = os.path.join(project_root, 'temp', temp_file_name)

                # 确保临时目录存在
                os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)

                # 写入分配给当前虚拟机的Apple ID到临时文件
                with open(temp_file_path, 'w', encoding='utf-8') as f:
                    f.write(vm_apple_ids[0])

                # logger.info(f"[线程] 创建临时文件: {temp_file_path}，包含 1 个Apple ID")

                # 直接传输文件，不校验远端目录是否存在
                # logger.info(f"[线程] 直接传输Apple ID文件到虚拟机 {vm_name}，不校验远端目录")

                # 使用SCP传输文件到虚拟机的Documents目录，文件名固定为appleid.txt
                remote_file_path = f"{appleidtxt_path}appleid.txt"

                # 使用SFTP传输Apple ID文件
                success, message = send_file_via_sftp(temp_file_path, remote_file_path, vm_ip, vm_username, timeout=60)

                if success:
                    logger.info(f"[线程] 成功传输Apple ID文件到虚拟机 {vm_name} 的Documents目录")

                    # 执行登录脚本
                    script_success = False
                    script_message = ""

                    try:
                        # 查找login_imessage.scpt脚本
                        script_found = False
                        script_path = None

                        for script_dir in script_upload_dirs:
                            # 直接使用完整路径
                            potential_script_path = os.path.join(script_dir, f'{login_imessage}')
                            # logger.info(f"[线程] 检查本地脚本路径: {potential_script_path}")
                            if os.path.exists(potential_script_path):
                                script_path = potential_script_path
                                script_found = True
                                logger.info(f"[线程] 找到本地登录脚本: {script_path}")
                                break

                        if script_found:
                            # 先传输脚本到虚拟机，然后调用API执行
                            dir_remote_script_path = f"{scpt_script_remote_path}{login_imessage}"
                            # 使用SFTP传输登录脚本
                            script_success_transfer, script_message_transfer = send_file_via_sftp(script_path,
                                                                                                  dir_remote_script_path,
                                                                                                  vm_ip, vm_username,
                                                                                                  timeout=60)

                            if script_success_transfer:
                                # logger.info(f"[线程] 成功传输登录脚本到虚拟机 {vm_name}")

                                # 调用客户端8787端口API执行登录脚本
                                try:
                                    script_api_url = f"http://{vm_ip}:8787/run?path={dir_remote_script_path}"
                                    logger.info(f"[线程] 调用客户端API执行登录脚本: {script_api_url}")

                                    response = requests.get(script_api_url, timeout=300)

                                    if response.status_code == 200:
                                        script_output = response.text.strip()
                                        logger.info(f"[线程] 虚拟机 {vm_name} 登录脚本执行成功，输出: {script_output}")
                                        script_success = True
                                        script_message = f"登录脚本执行成功: {script_output}"
                                    else:
                                        #  logger.error(f"[线程] 虚拟机 {vm_name} 登录脚本执行失败，HTTP状态码: {response.status_code}")
                                        script_message = f"登录脚本执行失败: HTTP {response.status_code}"

                                except requests.exceptions.Timeout:
                                    # logger.error(f"[线程] 虚拟机 {vm_name} 登录脚本执行超时")
                                    script_message = "登录脚本执行超时"
                                except requests.exceptions.ConnectionError:
                                    # logger.error(f"[线程] 虚拟机 {vm_name} 无法连接到8787端口")
                                    script_message = "无法连接到客户端8787端口"
                                except Exception as api_error:
                                    # logger.error(f"[线程] 虚拟机 {vm_name} API调用异常: {str(api_error)}")
                                    script_message = f"API调用异常: {str(api_error)}"
                            else:
                                script_error = script_transfer_result.stderr.strip() if script_transfer_result.stderr else '未知错误'
                                # logger.error(f"[线程] 传输登录脚本到虚拟机 {vm_name} 失败: {script_error}")
                                script_message = f"登录脚本传输失败: {script_error}"
                        else:
                            # logger.warning(f"[线程] 未找到login_imessage.scpt登录脚本")
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
                            'apple_id_range': f"{i + 1}",
                            'script_executed': script_success,
                            'script_message': script_message
                        })
                else:
                    error_msg = result.stderr.strip() if result.stderr else '未知错误'
                    # logger.error(f"[线程] 传输Apple ID文件到虚拟机 {vm_name} 失败: {error_msg}")
                    with results_lock:
                        results.append({
                            'vm_name': vm_name,
                            'success': False,
                            'message': f'传输失败: {error_msg}',
                            'apple_id_count': len(vm_apple_ids),
                            'apple_id_range': f"{i + 1}"
                        })

                # 清理临时文件
                try:
                    os.remove(temp_file_path)
                # logger.info(f"[线程] 清理临时文件: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"[线程] 清理临时文件失败: {str(e)}")

            except subprocess.TimeoutExpired:
                # logger.error(f"[线程] 传输Apple ID文件到虚拟机 {vm_name} 超时")
                with results_lock:
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': '传输超时（60秒）'
                    })
            except Exception as e:
                #  logger.error(f"[线程] 处理虚拟机 {vm_name} 时发生错误: {str(e)}")
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
                                        logger.info(
                                            f"使用 {encoding} 编码读取现有备份文件，包含 {len(existing_backup_ids)} 个Apple ID")
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
                        logger.info(
                            f"备份文件总计包含 {len(unique_backup_ids)} 个Apple ID（新增 {len(used_apple_ids)} 个）")

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

                        logger.info(
                            f"已从原文件中移除 {len(used_apple_ids)} 个已使用的Apple ID（使用 {write_encoding} 编码）")

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

        logger.info(
            f"Apple ID统计信息 - 文件: {filename}, 可用ID(有效): {available_count}, 已使用: {used_count}, 无效: {invalid_count}, 总计: {total_count}")

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

                logger.info(f"虚拟机 {vm_name} 分配第 {i + 1} 行文本: {vm_text_lines[0]}")

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

                # 使用SFTP传输文件到虚拟机
                success, message = send_file_via_sftp(temp_file_path, remote_file_path, vm_ip, vm_username, timeout=60)

                if success:
                    logger.info(f"成功传输文本文件到虚拟机 {vm_name}")
                    results.append({
                        'vm_name': vm_name,
                        'success': True,
                        'message': f'文本文件已成功传输到虚拟机 {vm_name}',
                        'remote_path': remote_file_path,
                        'line_count': len(vm_text_lines),
                        'line_range': f"{i + 1}",
                        'text_lines': vm_text_lines  # 返回分配给该虚拟机的具体文本行
                    })
                else:
                    logger.error(f"传输文本文件到虚拟机 {vm_name} 失败: {message}")
                    results.append({
                        'vm_name': vm_name,
                        'success': False,
                        'message': f'传输失败: {error_msg}',
                        'line_count': len(vm_text_lines),
                        'line_range': f"{i + 1}"
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
                result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30, encoding='utf-8',
                                        errors='ignore')

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
                            # logger.debug(f"获取到运行中虚拟机IP: {ip} ({vm_name})")
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
        script_name = data.get('script_name', f'{login_imessage}')

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

atexit.register(cleanup_on_exit)


# 信号处理


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