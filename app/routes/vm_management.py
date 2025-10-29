import os
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template
from app.utils.vm_utils import *
from app.utils.ssh_utils import SSHClient
from app.utils.vm_cache import *
from app.utils.log_utils import *
from config import *
# 导入带session超时检查的login_required装饰器
from app.utils.common_utils import login_required

# 创建虚拟机信息管理蓝图
vm_management_bp = Blueprint('vm_management', __name__)

# 导入日志工具
from app.utils.log_utils import get_logger

# 获取日志记录器
logger = get_logger(__name__)


@vm_management_bp.route('/api/vm_info_list')
@login_required
def api_vm_info_list():
    """获取虚拟机信息列表"""
    try:
        vm_dir = vm_base_dir
        vms = []

        # 批量获取运行中的虚拟机列表（只执行一次vmrun命令）
        running_vms = set()
        try:
            vmrun_path = get_vmrun_path()

            list_cmd = [vmrun_path, 'list']
            result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30, encoding='utf-8',
                                    errors='ignore')

            if result.returncode == 0:
                running_vms = set(result.stdout.strip().split('\n')[1:])
        except Exception as e:
            logger.info(f"[DEBUG] 获取运行中虚拟机列表失败: {str(e)}")

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
        logger.info(f"[DEBUG] 获取虚拟机信息列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取虚拟机信息失败: {str(e)}'
        })


@vm_management_bp.route('/api/vm_list')
@login_required
def api_vm_list():
    """获取虚拟机列表"""
    # logger.info("收到获取虚拟机列表API请求")
    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        logger.debug(f"分页参数 - 页码: {page}, 每页大小: {page_size}")
        vm_dir = vm_base_dir
        vms = []
        stats = {'total': 0, 'running': 0, 'stopped': 0, 'online': 0}

        logger.debug(f"开始扫描虚拟机目录: {vm_dir}")

        # 批量获取运行中的虚拟机列表（只执行一次vmrun命令）
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


@vm_management_bp.route('/api/vm_details/<vm_name>')
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


@vm_management_bp.route('/api/vm_ip_status/<vm_name>')
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
        logger.info(f"[DEBUG] 获取虚拟机IP状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取虚拟机IP状态失败: {str(e)}'
        })


@vm_management_bp.route('/api/vm/public_ip/<vm_name>')
@login_required
def api_vm_public_ip(vm_name):
    """获取虚拟机公网IP地址"""
    # logger.info(f"收到获取虚拟机 {vm_name} 公网IP的请求")
    try:
        # 获取虚拟机IP地址
        # logger.debug(f"开始获取虚拟机 {vm_name} 的IP地址")
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            logger.warning(f"无法获取虚拟机 {vm_name} 的IP地址")
            return jsonify({
                'success': False,
                'message': '无法获取虚拟机IP地址'
            })

       # logger.info(f"虚拟机 {vm_name} 的局域网IP地址: {vm_ip}")

        # 检查SSH连接
        # logger.debug(f"检查虚拟机 {vm_name} 的SSH连接")
        if not check_ssh_connectivity(vm_ip, vm_username):
            logger.warning(f"虚拟机 {vm_name} SSH连接失败")
            return jsonify({
                'success': False,
                'message': 'SSH连接失败，无法获取公网IP'
            })

        # logger.info(f"虚拟机 {vm_name} SSH连接成功")

        # 构建脚本路径
        script_path = f"{sh_script_remote_path}getipaddress.sh"
        # logger.debug(f"执行脚本路径: {script_path}")

        # 通过SSH执行脚本获取公网IP
        # logger.info(f"开始执行获取公网IP脚本: {vm_name}")
        success, output, log = execute_remote_script(vm_ip, vm_username, script_path)

        # logger.info(f"脚本执行结果 - 成功: {success}, 输出: {output}")

        if success:
            # 解析输出，提取IP地址
            public_ip = output.strip()
            # logger.info(f"获取到的公网IP: {public_ip}")
            # 简单验证IP格式
            if is_valid_ip(public_ip):
              #  logger.info(f"虚拟机 {vm_name} 公网IP获取成功: {public_ip}")
                return jsonify({
                    'success': True,
                    'vm_name': vm_name,
                    'public_ip': public_ip
                })
            else:
                logger.warning(f"获取到的公网IP格式无效: {public_ip}")
                return jsonify({
                    'success': False,
                    'message': f'获取到的公网IP格式无效: {public_ip}'
                })
        else:
            logger.error(f"执行脚本失败: {output}")
            return jsonify({
                'success': False,
                'message': f'执行脚本失败: {output}'
            })

    except Exception as e:
        logger.error(f"获取虚拟机公网IP失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取虚拟机公网IP失败: {str(e)}'
        })


@vm_management_bp.route('/api/vm_online_status', methods=['POST'])
@login_required
def api_vm_online_status():
    """异步获取虚拟机在线状态（只处理运行中的虚拟机）"""
    # logger.info("收到异步获取虚拟机在线状态请求")
    try:
        data = request.get_json()
        vm_names = data.get('vm_names', [])

        if not vm_names:
            logger.warning("缺少虚拟机名称")
            return jsonify({'success': False, 'message': '缺少虚拟机名称'})

        # logger.debug(f"开始异步获取 {len(vm_names)} 个虚拟机的在线状态")

        results = {}
        for vm_name in vm_names:
            try:
                #  logger.debug(f"获取虚拟机 {vm_name} 的在线状态")
                online_status = get_vm_online_status(vm_name)
                results[vm_name] = {
                    'online_status': online_status['status'],
                    'online_reason': online_status['reason'],
                    'ip': online_status['ip'],
                    'ssh_trust': online_status['ssh_trust'],
                    'ssh_port_open': online_status.get('ssh_port_open', False)
                }
            #  logger.debug(f"虚拟机 {vm_name} 在线状态: {online_status['status']}")
            except Exception as e:
                #  logger.error(f"获取虚拟机 {vm_name} 在线状态失败: {str(e)}")
                results[vm_name] = {
                    'online_status': 'error',
                    'online_reason': f'获取状态失败: {str(e)}',
                    'ip': None,
                    'ssh_trust': False
                }

        # logger.info(f"异步获取完成，共处理 {len(results)} 个虚拟机")
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


@vm_management_bp.route('/api/vm_ip_monitor', methods=['POST'])
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
        logger.info(f"[DEBUG] 批量监控IP状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量监控失败: {str(e)}'
        })


@vm_management_bp.route('/api/vm_start', methods=['POST'])
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

        logger.info(f"[DEBUG] 启动虚拟机 {vm_name}")

        start_cmd = [vmrun_path, 'start', vm_file, 'nogui']
        # logger.info(f"[DEBUG] 启动命令: {' '.join(start_cmd)}")

        # 记录命令开始时间
        start_time = datetime.now()

        result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=60)

        # 记录命令结束时间
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        if result.stderr:
            logger.info(f"[DEBUG] 启动命令错误: {result.stderr}")

        if result.returncode == 0:
            logger.info(f"[DEBUG] 虚拟机 {vm_name} 启动成功")
            return jsonify({'success': True, 'message': '虚拟机启动成功'})
        else:
            logger.info(f"[DEBUG] 虚拟机 {vm_name} 启动失败: {result.stderr}")
            return jsonify({'success': False, 'message': f'启动失败: {result.stderr}'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'启动失败: {str(e)}'})


@vm_management_bp.route('/api/vm_stop', methods=['POST'])
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

        logger.info(f"[DEBUG] 停止虚拟机 {vm_name}")
        logger.info(f"[DEBUG] 虚拟机文件路径: {vm_file}")
        logger.info(f"[DEBUG] vmrun路径: {vmrun_path}")

        stop_cmd = [vmrun_path, 'stop', vm_file, 'hard']
        logger.info(f"[DEBUG] 停止命令: {' '.join(stop_cmd)}")

        # 记录命令开始时间
        start_time = datetime.now()
        logger.info(f"[DEBUG] 停止命令开始时间: {start_time}")

        result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=60)

        # 记录命令结束时间
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"[DEBUG] 停止命令结束时间: {end_time}")
        logger.info(f"[DEBUG] 停止命令执行时长: {duration} 秒")
        logger.info(f"[DEBUG] 停止命令返回码: {result.returncode}")
        logger.info(f"[DEBUG] 停止命令输出: {result.stdout}")
        if result.stderr:
            logger.info(f"[DEBUG] 停止命令错误: {result.stderr}")

        if result.returncode == 0:
            logger.info(f"[DEBUG] 虚拟机 {vm_name} 停止成功")
            return jsonify({'success': True, 'message': '虚拟机停止成功'})
        else:
            logger.info(f"[DEBUG] 虚拟机 {vm_name} 停止失败: {result.stderr}")
            return jsonify({'success': False, 'message': f'停止失败: {result.stderr}'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'停止失败: {str(e)}'})


@vm_management_bp.route('/api/vm_restart', methods=['POST'])
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

        logger.info(f"[DEBUG] 重启虚拟机 {vm_name}")
        logger.info(f"[DEBUG] 虚拟机文件路径: {vm_file}")
        logger.info(f"[DEBUG] vmrun路径: {vmrun_path}")

        # 先停止虚拟机
        stop_cmd = [vmrun_path, 'stop', vm_file, 'hard']
        logger.info(f"[DEBUG] 重启-停止命令: {' '.join(stop_cmd)}")

        # 记录停止命令开始时间
        stop_start_time = datetime.now()
        logger.info(f"[DEBUG] 重启-停止命令开始时间: {stop_start_time}")

        stop_result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=60)

        # 记录停止命令结束时间
        stop_end_time = datetime.now()
        stop_duration = (stop_end_time - stop_start_time).total_seconds()
        logger.info(f"[DEBUG] 重启-停止命令结束时间: {stop_end_time}")
        logger.info(f"[DEBUG] 重启-停止命令执行时长: {stop_duration} 秒")
        logger.info(f"[DEBUG] 重启-停止命令返回码: {stop_result.returncode}")
        logger.info(f"[DEBUG] 重启-停止命令输出: {stop_result.stdout}")
        if stop_result.stderr:
            logger.info(f"[DEBUG] 重启-停止命令错误: {stop_result.stderr}")
        logger.info(f"[DEBUG] 等待2秒后启动...")
        time.sleep(2)

        # 启动虚拟机
        start_cmd = [vmrun_path, 'start', vm_file, 'nogui']
        #  logger.info(f"[DEBUG] 重启-启动命令: {' '.join(start_cmd)}")

        # 记录启动命令开始时间
        start_start_time = datetime.now()
        # logger.info(f"[DEBUG] 重启-启动命令开始时间: {start_start_time}")

        start_result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=60)

        # 记录启动命令结束时间
        start_end_time = datetime.now()
        start_duration = (start_end_time - start_start_time).total_seconds()
        if start_result.stderr:
            logger.info(f"[DEBUG] 重启-启动命令错误: {start_result.stderr}")

        if start_result.returncode == 0:
            #  logger.info(f"[DEBUG] 虚拟机 {vm_name} 重启成功")
            return jsonify({'success': True, 'message': '虚拟机重启成功'})
        else:
            logger.info(f"[DEBUG] 虚拟机 {vm_name} 重启失败: {start_result.stderr}")
            return jsonify({'success': False, 'message': f'重启失败: {start_result.stderr}'})

    except Exception as e:
        logger.info(f"[DEBUG] 重启虚拟机失败: {str(e)}")
        return jsonify({'success': False, 'message': f'重启失败: {str(e)}'})


@vm_management_bp.route('/api/vm_info/<vm_name>')
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


# 修改虚拟机名称
@vm_management_bp.route('/api/update_vm_name', methods=['POST'])
@login_required
def api_update_vm_name():
    """更新虚拟机名称 - 修改displayName参数并重命名相关文件"""
    try:
        data = request.get_json()
        original_name = data.get('original_name')
        new_name = data.get('new_name')

        if not original_name or not new_name:
            return jsonify({'success': False, 'message': '缺少原始名称或新名称'})

        if original_name == new_name:
            return jsonify({'success': False, 'message': '新名称与原名称相同'})

        # 验证新名称的合法性
        invalid_chars = r'[\\/:*?"<>|]'
        if re.search(invalid_chars, new_name):
            return jsonify({'success': False, 'message': '虚拟机名称不能包含特殊字符：\\ / : * ? " < > |'})

        # 查找原始虚拟机文件
        original_vm_file = find_vm_file(original_name)
        if not original_vm_file:
            return jsonify({'success': False, 'message': f'找不到虚拟机文件: {original_name}'})

        # 检查虚拟机是否正在运行
        vm_status = get_vm_status(original_vm_file)
        if vm_status == 'running' or vm_status == 'starting':
            return jsonify({'success': False, 'message': '无法重命名正在运行的虚拟机，请先停止虚拟机'})

        logger.info(f'开始修改虚拟机名称: {original_name} -> {new_name}')

        # 获取虚拟机目录
        vm_dir = os.path.dirname(original_vm_file)

        # 备份原始vmx文件
        backup_file = original_vm_file + '.backup.' + datetime.now().strftime('%Y%m%d_%H%M%S')
        try:
            shutil.copy2(original_vm_file, backup_file)
            logger.info(f'VMX文件备份成功: {backup_file}')
        except Exception as e:
            logger.error(f'备份VMX文件失败: {str(e)}')
            return jsonify({'success': False, 'message': f'备份VMX文件失败: {str(e)}'})

        renamed_files = []  # 记录已重命名的文件，用于回滚

        try:
            # 1. 修改VMX文件中的displayName参数和编码
            success, message = update_vmx_display_name(original_vm_file, new_name)
            if not success:
                logger.error(f'更新VMX文件失败: {message}')
                return jsonify({'success': False, 'message': f'更新VMX文件失败: {message}'})

            logger.info(f'VMX文件displayName和编码更新成功: {original_vm_file}')

            # 2. 重命名相关文件
            file_extensions = ['.vmx']

            for ext in file_extensions:
                old_file = os.path.join(vm_dir, original_name + ext)
                new_file = os.path.join(vm_dir, new_name + ext)

                if os.path.exists(old_file):
                    try:
                        os.rename(old_file, new_file)
                        renamed_files.append((old_file, new_file))
                        logger.info(f'文件重命名成功: {old_file} -> {new_file}')
                    except Exception as e:
                        logger.error(f'重命名文件失败: {old_file} -> {new_file}, 错误: {str(e)}')
                        raise Exception(f'重命名文件失败: {ext} 文件')

            # 3. 更新VMX文件路径（如果文件被重命名）
            new_vm_file = os.path.join(vm_dir, new_name + '.vmx')
            if new_vm_file != original_vm_file and os.path.exists(new_vm_file):
                # 更新VMX文件中的文件路径引用，使用智能编码检测
                content, encoding = read_vmx_file_smart(new_vm_file)

                if content is None:
                    logger.error(f'无法使用任何编码读取VMX文件: {new_vm_file}')
                else:
                    logger.info(f'成功使用 {encoding} 编码读取VMX文件进行路径更新')
                    logger.info(f'VMX文件路径引用更新成功: {new_vm_file}')

        except Exception as e:
            logger.error(f'重命名过程中发生错误: {str(e)}')

            # 回滚已重命名的文件
            for old_file, new_file in reversed(renamed_files):
                try:
                    if os.path.exists(new_file):
                        os.rename(new_file, old_file)
                        logger.info(f'回滚文件: {new_file} -> {old_file}')
                except:
                    pass

            # 恢复备份文件
            try:
                shutil.copy2(backup_file, original_vm_file)
                os.remove(backup_file)
                logger.info('已恢复VMX备份文件')
            except:
                pass

            return jsonify({'success': False, 'message': f'重命名失败: {str(e)}'})

        logger.info(f'虚拟机名称修改完成: {original_name} -> {new_name}')

        return jsonify({
            'success': True,
            'message': f'虚拟机名称修改成功: {original_name} -> {new_name}',
            'original_name': original_name,
            'new_name': new_name,
            'backup_file': backup_file,
            'renamed_files': len(renamed_files)
        })

    except Exception as e:
        logger.error(f'更新虚拟机名称失败: {str(e)}')
        return jsonify({'success': False, 'message': f'更新虚拟机名称失败: {str(e)}'})


@vm_management_bp.route('/api/vm_delete', methods=['POST'])
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
                    shutil.rmtree(vm_dir)
                    deleted_vms.append(vm_name)
                    logger.info(f"[DEBUG] 成功删除虚拟机: {vm_name}")
                else:
                    failed_vms.append(f'{vm_name} (文件夹不存在)')

            except Exception as e:
                failed_vms.append(f'{vm_name} ({str(e)})')
                logger.info(f"[DEBUG] 删除虚拟机失败 {vm_name}: {str(e)}")

        return jsonify({
            'success': True,
            'deleted_vms': deleted_vms,
            'failed_vms': failed_vms,
            'message': f'成功删除 {len(deleted_vms)} 个虚拟机，失败 {len(failed_vms)} 个'
        })

    except Exception as e:
        logger.info(f"[DEBUG] 删除虚拟机API失败: {str(e)}")
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})




@vm_management_bp.route('/api/get_wuma_info', methods=['POST'])
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
        result = execute_remote_script(vm_ip, 'wx', f'{sh_script_remote_path}run_debug_wuma.sh')
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


@vm_management_bp.route('/api/get_ju_info', methods=['POST'])
@login_required
def api_get_ju_info():
    """获取JU值信息API - 通过SSH互信执行家目录脚本"""
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')

        if not vm_name:
            return jsonify({'success': False, 'error': '缺少虚拟机名称参数'})

        # logger.debug(f"开始获取虚拟机 {vm_name} 的JU值信息")

        # 获取虚拟机IP地址
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip or vm_ip == '获取中...' or vm_ip == '-':
            return jsonify({'success': False, 'error': f'无法获取虚拟机 {vm_name} 的IP地址'})

        logger.debug(f"虚拟机 {vm_name} 的IP地址: {vm_ip}")

        # 通过SSH互信执行家目录脚本
        result = execute_remote_script(vm_ip, 'wx', f'{sh_script_remote_path}run_debug_ju.sh')
        if len(result) == 3:
            success, output, ssh_log = result
        elif len(result) == 2:
            success, output = result
        else:
            success, output = False, "未知错误"

        if success:
            # logger.info(f"成功获取虚拟机 {vm_name} 的JU值信息:")
            return jsonify({'success': True, 'output': output})
        else:
            logger.error(f"获取虚拟机 {vm_name} 的JU值信息失败: {output}")
            return jsonify({'success': False, 'error': output})

    except Exception as e:
        logger.error(f"获取JU值信息时发生异常: {str(e)}")
        return jsonify({'success': False, 'error': f'获取JU值信息时发生异常: {str(e)}'})


@vm_management_bp.route('/api/vm_chengpin_online_status', methods=['POST'])
@login_required
def api_vm_chengpin_online_status():
    """获取成品虚拟机在线状态"""
    # logger.info("收到获取成品虚拟机在线状态请求")
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
           #     logger.info(f"[DEBUG] 成品虚拟机 {vm_name} 在线状态结果: {online_status}")
            except Exception as e:
                logger.error(f"获取虚拟机 {vm_name} 在线状态失败: {str(e)}")
                logger.info(f"[DEBUG] 成品虚拟机 {vm_name} 获取状态失败: {str(e)}")
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


@vm_management_bp.route('/api/ssh_chengpin_trust', methods=['POST'])
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

        if success:
            # 清理虚拟机状态缓存，确保下次检查时获取最新状态
            vm_cache.clear_cache(vm_name, 'online_status')

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


@vm_management_bp.route('/api/vm_10_12_online_status', methods=['POST'])
@login_required
def api_vm_10_12_online_status():
    """获取10.12目录虚拟机在线状态"""
    global logger
    # logger.info("收到获取10.12目录虚拟机在线状态请求")
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
                logger.info(f"[DEBUG] 10.12虚拟机 {vm_name} 在线状态结果: {online_status}")
            except Exception as e:
                logger.error(f"获取虚拟机 {vm_name} 在线状态失败: {str(e)}")
                logger.info(f"[DEBUG] 10.12虚拟机 {vm_name} 获取状态失败: {str(e)}")
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


@vm_management_bp.route('/api/ssh_10_12_trust', methods=['POST'])
@login_required
def api_ssh_10_12_trust():
    """设置10.12目录虚拟机SSH互信"""
    # logger.info("收到设置10.12目录虚拟机SSH互信请求")
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

        if success:
            # 清理虚拟机状态缓存，确保下次检查时获取最新状态
            vm_cache.clear_cache(vm_name, 'online_status')

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
