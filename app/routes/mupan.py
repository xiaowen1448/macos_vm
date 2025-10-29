import os
import re
import json
from datetime import datetime
import concurrent.futures
import subprocess
from flask import Blueprint, request, jsonify
import logging
from config import *
from app.utils.ssh_utils import setup_ssh_trust
# 导入带session超时检查的login_required装饰器
from app.utils.common_utils import login_required

# 创建蓝图
mupan_bp = Blueprint('mupan', __name__)

# 导入日志工具
from app.utils.log_utils import get_logger

# 获取日志记录器
logger = get_logger(__name__)

# VMware工具路径配置
VMRUN_PATH = f"{vmrun_path}"

def get_vmrun_path():
    """获取vmrun工具路径"""
    return vmrun_path

def get_vm_status(vm_path):
    """获取虚拟机状态"""
    try:
        vmrun_path = get_vmrun_path()
        
        # 执行vmrun list命令获取运行中的虚拟机列表
        list_cmd = [vmrun_path, 'list']
        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30, 
                               encoding='utf-8', errors='ignore')

        if result.stderr:
            logger.info(f"[DEBUG] vmrun list命令错误: {result.stderr}")

        if result.returncode == 0:
            running_vms = result.stdout.strip().split('\n')[1:]  # 跳过标题行
            vm_name = os.path.splitext(os.path.basename(vm_path))[0]

            # 检查虚拟机是否在运行列表中
            vm_found = False
            for vm in running_vms:
                if vm.strip() and vm_name in vm:
                    vm_found = True
                    break

            if vm_found:
                # 检查虚拟机是否正在启动过程中
                try:
                    # 尝试获取虚拟机IP，如果获取失败可能正在启动
                    cmd = [vmrun_path, 'getGuestIPAddress', vm_path, '-wait']
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        return "running"
                    else:
                        # 获取IP失败，可能正在启动中
                        return "starting"
                except:
                    # 出错也视为运行中
                    return "running"
            else:
                # 检查虚拟机文件是否存在
                if os.path.exists(vm_path):
                    return "stopped"
                else:
                    return "未知"
        else:
            # vmrun命令执行失败
            return "未知"
    except Exception as e:
        logger.error(f"获取虚拟机状态失败: {str(e)}")
        return "未知"


@mupan_bp.route('/api/default-template-dir')
def get_default_template_dir():
    """获取默认母盘目录配置API"""
    try:
        return jsonify({
            'success': True,
            'template_dir': template_dir
        })
    except Exception as e:
        logger.error(f"获取默认母盘目录失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取默认母盘目录失败: {str(e)}'
        })

@mupan_bp.route('/api/mupan_size/<vm_name>')
def get_mupan_size(vm_name):
    """获取母盘大小API"""
    try:
        # 从请求参数中获取母盘目录
        template_vm_dir = request.args.get('template_vm_dir')
        if not template_vm_dir:
            return jsonify({
                'success': False,
                'message': '缺少母盘目录参数'
            })
        
        # 构建母盘路径
        mupan_path = os.path.join(template_vm_dir, vm_name)
        
        # 检查母盘路径是否存在
        if not os.path.exists(mupan_path):
            return jsonify({
                'success': False,
                'message': f'母盘目录不存在: {vm_name}'
            })
        
        # 计算母盘大小（以GB为单位）
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(mupan_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    # 跳过符号链接
                    if os.path.isfile(filepath) and not os.path.islink(filepath):
                        try:
                            total_size += os.path.getsize(filepath)
                        except (OSError, IOError) as e:
                            logger.warning(f"无法获取文件大小: {filepath}, 错误: {str(e)}")
            
            # 转换为GB并保留一位小数
            size_gb = round(total_size / (1024 ** 3), 1)
            
            return jsonify({
                'success': True,
                'size': size_gb
            })
        except Exception as e:
            logger.error(f"计算母盘大小失败: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'计算母盘大小失败: {str(e)}'
            })
            
    except Exception as e:
        logger.error(f"获取母盘大小失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取母盘大小失败: {str(e)}'
        })


import concurrent.futures

@mupan_bp.route('/api/mupan_list')
@login_required
def api_mupan_list():
    """获取母盘虚拟机列表"""
    logger.info("收到母盘虚拟机列表请求")
    try:
        # 扫描TemplateVM目录
        template_vms = []
        vm_info_list = []

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

                        # 获取vmx文件创建时间
                        try:
                            create_time = datetime.fromtimestamp(os.path.getmtime(vm_path))
                            create_time_str = create_time.strftime('%Y-%m-%d %H:%M:%S')
                            logger.info(f"创建时间: {create_time_str}")
                        except:
                            create_time_str = "未知"
                            logger.warning(f"无法获取创建时间: {vm_path}")

                        # 收集虚拟机信息，稍后并行获取状态
                        vm_info = {
                            'name': vm_name,
                            'path': vm_path,
                            'system_version': system_version,
                            'create_time': create_time_str
                        }
                        vm_info_list.append(vm_info)
                        logger.info(f"收集虚拟机数据: {vm_info}")

            # 并行获取虚拟机状态，提高性能
            logger.info(f"开始并行获取{len(vm_info_list)}个虚拟机状态")
            # 限制线程池大小，避免创建过多线程
            max_workers = min(10, len(vm_info_list))
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有状态检查任务
                future_to_vm = {executor.submit(get_vm_status, vm['path']): vm for vm in vm_info_list}
                
                # 收集结果
                for future in concurrent.futures.as_completed(future_to_vm):
                    vm = future_to_vm[future]
                    try:
                        vm_status = future.result()
                        logger.info(f"虚拟机 {vm['name']} 状态: {vm_status}")
                        
                        # 完整的虚拟机数据
                        vm_data = vm.copy()
                        vm_data['status'] = vm_status
                        template_vms.append(vm_data)
                    except Exception as e:
                        logger.error(f"获取虚拟机 {vm['name']} 状态失败: {str(e)}")
                        # 出错时设置状态为未知，但仍添加到列表中
                        vm_data = vm.copy()
                        vm_data['status'] = "未知"
                        template_vms.append(vm_data)

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



# VMware工具路径配置
VMRUN_PATH = f"{vmrun_path}"

def parse_vmsd_file(vmsd_path):
    """解析vmsd文件获取快照信息"""
    snapshots = {}
    
    if not os.path.exists(vmsd_path):
        logger.warning(f"vmsd文件不存在: {vmsd_path}")
        return snapshots
    
    try:
        with open(vmsd_path, 'r', encoding='gb2312', errors='ignore') as f:
            content = f.read()
        
        # 使用正则表达式匹配快照信息
        snapshot_pattern = r'snapshot(\d+)\.(\w+(?:\.\w+)*)\s*=\s*"([^"]*)"'
        matches = re.findall(snapshot_pattern, content)
        
        for match in matches:
            snapshot_id = match[0]
            property_name = match[1]
            property_value = match[2]
            
            if snapshot_id not in snapshots:
                snapshots[snapshot_id] = {}
            
            # 处理嵌套属性，如disk0.fileName
            if '.' in property_name:
                parts = property_name.split('.')
                current = snapshots[snapshot_id]
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = property_value
            else:
                snapshots[snapshot_id][property_name] = property_value
        
        logger.info(f"解析vmsd文件成功，找到 {len(snapshots)} 个快照")
        return snapshots
        
    except Exception as e:
        logger.error(f"解析vmsd文件失败: {str(e)}")
        return {}

def get_vmsn_create_time(template_path, filename):
    """获取vmsn文件的创建时间"""
    try:
        vmsn_path = os.path.join(template_path, filename)
        if os.path.exists(vmsn_path):
            # 获取文件的创建时间
            create_timestamp = os.path.getctime(vmsn_path)
            create_time = datetime.fromtimestamp(create_timestamp)
            return create_time.strftime('%Y-%m-%d %H:%M:%S')
        else:
            logger.warning(f"vmsn文件不存在: {vmsn_path}")
            return '文件不存在'
    except Exception as e:
        logger.error(f"获取vmsn文件创建时间失败: {str(e)}")
        return '获取失败'

def parse_vmdk_file(vmdk_path):
    """解析vmdk文件获取parentFileNameHint信息"""
    try:
        with open(vmdk_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # 查找parentFileNameHint
        pattern = r'parentFileNameHint\s*=\s*"([^"]*)"'
        match = re.search(pattern, content)
        
        if match:
            return match.group(1)
        return None
        
    except Exception as e:
        logger.error(f"解析vmdk文件失败 {vmdk_path}: {str(e)}")
        return None

def check_snapshot_clones(snapshot_info):
    """从vmsd文件中检查快照的克隆虚拟机是否存在"""
    clone_paths = []
    existing_clones = []
    
    # 获取克隆数量
    num_clones = int(snapshot_info.get('numClones', 0))
    
    if num_clones == 0:
        return clone_paths, existing_clones
    
    # 获取所有克隆路径
    for i in range(num_clones):
        clone_key = f'clone{i}'
        if clone_key in snapshot_info:
            clone_path = snapshot_info[clone_key]
            clone_paths.append(clone_path)
            
            # 检查克隆虚拟机目录是否存在
            clone_dir = os.path.dirname(clone_path)
            if os.path.exists(clone_dir):
                existing_clones.append(clone_path)
                logger.info(f"发现存在的克隆虚拟机: {clone_path}")
            else:
                logger.info(f"克隆虚拟机目录不存在: {clone_dir}")
    
    return clone_paths, existing_clones

def get_template_vm_snapshots(template_name, template_vm_dir=None):
    """获取指定母盘的快照列表"""
    if not template_vm_dir:
        return {'success': False, 'message': '缺少母盘目录参数'}
        
    template_path = os.path.join(template_vm_dir, template_name)
    
    if not os.path.exists(template_path):
        return {'success': False, 'message': f'母盘目录不存在: {template_name}'}
    
    # 查找vmsd文件
    vmsd_file = None
    for file in os.listdir(template_path):
        if file.endswith('.vmsd'):
            vmsd_file = os.path.join(template_path, file)
            break
    
    if not vmsd_file:
        return {'success': False, 'message': f'未找到vmsd文件: {template_name}'}
    
    # 解析快照信息
    snapshots_data = parse_vmsd_file(vmsd_file)
    
    if not snapshots_data:
        return {'success': True, 'snapshots': []}
    
    # 从config.py导入clone_dir配置
    from config import clone_dir
    
    # 处理快照数据
    snapshots = []
    for snapshot_id, snapshot_info in snapshots_data.items():
        if 'displayName' in snapshot_info:
            # 检查快照的克隆虚拟机
            clone_paths, existing_clones = check_snapshot_clones(snapshot_info)
            
            # 获取vmsn文件的创建时间
            create_time = '未知'
            if 'filename' in snapshot_info:
                vmsn_filename = snapshot_info['filename']
                create_time = get_vmsn_create_time(template_path, vmsn_filename)
            elif 'createTimeHigh' in snapshot_info and 'createTimeLow' in snapshot_info:
                try:
                    # VMware时间戳转换（备用方案）
                    high = int(snapshot_info['createTimeHigh'])
                    low = int(snapshot_info['createTimeLow'])
                    create_time = f"时间戳: {high}:{low}"
                except:
                    create_time = '未知'
            
            # 获取快照磁盘文件名
            disk_file = ''
            if 'disk0' in snapshot_info and isinstance(snapshot_info['disk0'], dict):
                disk_file = snapshot_info['disk0'].get('fileName', '')
            else:
                disk_file = snapshot_info.get('disk0fileName', '')
            
            # 检查vmdk关联关系
            vmdk_associated_vms = []
            if disk_file:
                vmdk_associated_vms = check_snapshot_vmdk_association(disk_file, clone_dir)
            
            # 提取存在的克隆虚拟机名称
            existing_vm_names = []
            for clone_path in existing_clones:
                vm_name = os.path.basename(os.path.dirname(clone_path))
                existing_vm_names.append(vm_name)
            
            # 合并所有关联的虚拟机（包括vmsd中的克隆和vmdk关联）
            all_associated_vms = list(set(existing_vm_names + vmdk_associated_vms))
            
            snapshot = {
                'id': snapshot_id,
                'name': snapshot_info['displayName'],
                'description': snapshot_info.get('description', ''),
                'create_time': create_time,
                'disk_file': disk_file,
                'clone_paths': clone_paths,
                'existing_clones': existing_clones,
                'used_by': existing_vm_names,
                'vmdk_associated_vms': vmdk_associated_vms,  # 新增：通过vmdk关联的虚拟机
                'all_associated_vms': all_associated_vms,    # 新增：所有关联的虚拟机
                'can_delete': len(all_associated_vms) == 0,  # 修改：只有没有任何关联时才能删除
                'clone_count': len(snapshot_info.get('clone0', '').split(',')) if snapshot_info.get('clone0') else 0,
                'vmsn_file': snapshot_info.get('filename', '')
            }
            
            # 添加关联虚拟机信息（保持向后兼容）
            clones = []
            clone_index = 0
            while f'clone{clone_index}' in snapshot_info:
                clone_path = snapshot_info[f'clone{clone_index}']
                if clone_path:
                    vm_name = os.path.basename(os.path.dirname(clone_path))
                    clones.append(vm_name)
                clone_index += 1
            
            snapshot['related_vms'] = all_associated_vms  # 使用所有关联的虚拟机
            snapshots.append(snapshot)
    
    return {'success': True, 'snapshots': snapshots}

@mupan_bp.route('/api/snapshots/<template_name>')
def get_snapshots(template_name):
    """获取母盘快照列表API"""
    logger.info(f"获取母盘快照列表: {template_name}")
    
    try:
        # 从请求参数中获取母盘目录
        template_vm_dir = request.args.get('template_vm_dir')
        if not template_vm_dir:
            return jsonify({
                'success': False,
                'message': '缺少母盘目录参数'
            })
            
        result = get_template_vm_snapshots(template_name, template_vm_dir)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"获取快照列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取快照列表失败: {str(e)}'
        })

@mupan_bp.route('/api/delete-snapshot', methods=['POST'])
def delete_snapshot():
    """删除快照API"""
    logger.info("收到删除快照请求")
    
    try:
        data = request.get_json()
        template_name = data.get('template_name')
        snapshot_name = data.get('snapshot_name')
        template_vm_dir = data.get('template_vm_dir')
        
        if not template_name or not snapshot_name or not template_vm_dir:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            })
        
        # 获取快照信息
        result = get_template_vm_snapshots(template_name, template_vm_dir)
        if not result['success']:
            return jsonify(result)
        
        # 查找要删除的快照
        target_snapshot = None
        for snapshot in result['snapshots']:
            if snapshot['name'] == snapshot_name:
                target_snapshot = snapshot
                break
        
        if not target_snapshot:
            return jsonify({
                'success': False,
                'message': '未找到指定快照'
            })
        
        # 检查是否可以删除
        if not target_snapshot['can_delete']:
            return jsonify({
                'success': False,
                'message': '该快照正在被虚拟机使用，无法删除'
            })
        
        # 删除快照
        success = delete_single_snapshot(template_name, target_snapshot, template_vm_dir)
        
        if success:
            logger.info(f"快照删除成功: {snapshot_name}")
            return jsonify({
                'success': True,
                'message': '快照删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '快照删除失败'
            })
        
    except Exception as e:
        logger.error(f"删除快照失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除快照失败: {str(e)}'
        })

@mupan_bp.route('/api/clean-invalid-snapshots/<template_name>', methods=['POST'])
def clean_invalid_snapshots(template_name):
    """清理失效快照API"""
    logger.info(f"收到清理失效快照请求: {template_name}")
    
    try:
        # 从请求数据中获取母盘目录
        data = request.get_json() or {}
        template_vm_dir = data.get('template_vm_dir')
        if not template_vm_dir:
            return jsonify({
                'success': False,
                'message': '缺少母盘目录参数'
            })
            
        # 获取快照列表
        result = get_template_vm_snapshots(template_name, template_vm_dir)
        if not result['success']:
            return jsonify(result)
        
        snapshots = result['snapshots']
        if not snapshots:
            return jsonify({
                'success': True, 
                'deleted_count': 0, 
                'kept_count': 0, 
                'message': '没有找到快照'
            })
        
        deleted_count = 0
        kept_count = 0
        deleted_snapshots = []
        skipped_snapshots = []
        failed_deletions = []
        
        # 遍历所有快照，只删除未被使用的快照
        for snapshot in snapshots:
            # 修改删除条件：检查所有关联的虚拟机
            if snapshot['can_delete'] and len(snapshot.get('all_associated_vms', [])) == 0:
                try:
                    # 删除快照
                    success = delete_single_snapshot(template_name, snapshot, template_vm_dir)
                    if success:
                        deleted_count += 1
                        deleted_snapshots.append(snapshot['name'])
                        logger.info(f"已删除失效快照: {snapshot['name']}")
                    else:
                        failed_deletions.append({
                            'name': snapshot['name'],
                            'error': '删除操作失败'
                        })
                        logger.warning(f"删除快照失败: {snapshot['name']}")
                except Exception as e:
                    failed_deletions.append({
                        'name': snapshot['name'],
                        'error': str(e)
                    })
                    logger.error(f"删除快照 {snapshot['name']} 时出错: {str(e)}")
            else:
                kept_count += 1
                associated_vms = snapshot.get('all_associated_vms', [])
                if len(associated_vms) > 0:
                    skipped_snapshots.append({
                        'name': snapshot['name'],
                        'used_by': associated_vms
                    })
                    logger.info(f"跳过删除快照 {snapshot['name']}，被以下虚拟机使用: {', '.join(associated_vms)}")
        
        message = f"清理完成，删除了 {deleted_count} 个失效快照"
        if skipped_snapshots:
            message += f"，跳过了 {len(skipped_snapshots)} 个正在使用的快照"
        if failed_deletions:
            message += f"，{len(failed_deletions)} 个快照删除失败"
        
        logger.info(f"清理完成 - 母盘: {template_name}, 删除: {deleted_count}, 保留: {kept_count}")
        return jsonify({
            'success': True, 
            'deleted_count': deleted_count, 
            'kept_count': kept_count,
            'deleted_snapshots': deleted_snapshots,
            'skipped_snapshots': skipped_snapshots,
            'failed_deletions': failed_deletions,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"清理失效快照失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'清理失效快照失败: {str(e)}'
        })

def delete_single_snapshot(template_name, snapshot, template_vm_dir):
    """删除单个快照"""
    try:
        template_path = os.path.join(template_vm_dir, template_name)
        vmx_file = os.path.join(template_path, f"{template_name}.vmx")
        
        if not os.path.exists(vmx_file):
            logger.error(f"vmx文件不存在: {vmx_file}")
            return False
        
        snapshot_name = snapshot['name']
        
        # 使用vmrun deleteSnapshot命令删除快照
        try:
            import subprocess
            cmd = [VMRUN_PATH, 'deleteSnapshot', vmx_file, snapshot_name]
            logger.info(f"执行删除快照命令: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                logger.info(f"成功删除快照: {snapshot_name}")
                return True
            else:
                error_msg = result.stderr.strip() if result.stderr else "未知错误"
                logger.error(f"vmrun删除快照失败: {error_msg}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"删除快照超时: {snapshot_name}")
            return False
        except Exception as e:
            logger.error(f"执行vmrun命令失败: {str(e)}")
            return False
        
    except Exception as e:
        logger.error(f"删除单个快照失败: {str(e)}")
        return False


def check_vmdk_parent_hint(vmdk_file_path):
    """检查vmdk文件的parentFileNameHint参数"""
    if not os.path.exists(vmdk_file_path):
        return None
    
    try:
        with open(vmdk_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # 只读取文件头部，通常parentFileNameHint在前几行
            for i, line in enumerate(f):
                if i > 50:  # 只检查前50行
                    break
                if 'parentFileNameHint' in line:
                    # 提取parentFileNameHint的值
                    match = re.search(r'parentFileNameHint\s*=\s*"([^"]*)"', line)
                    if match:
                        parent_hint = match.group(1)
                        # 提取文件名部分
                        parent_filename = os.path.basename(parent_hint)
                        logger.info(f"找到parentFileNameHint: {parent_filename}")
                        return parent_filename
        return None
    except Exception as e:
        logger.error(f"读取vmdk文件失败 {vmdk_file_path}: {str(e)}")
        return None

def check_snapshot_vmdk_association(snapshot_disk_file, clone_dir):
    """检查快照的vmdk文件是否与克隆虚拟机关联"""
    if not snapshot_disk_file or not clone_dir or not os.path.exists(clone_dir):
        return []
    
    associated_vms = []
    
    try:
        # 遍历克隆目录中的所有虚拟机目录
        for vm_name in os.listdir(clone_dir):
            vm_path = os.path.join(clone_dir, vm_name)
            if not os.path.isdir(vm_path):
                continue
            
            # 查找该虚拟机目录中的vmdk文件
            for file in os.listdir(vm_path):
                if file.endswith('.vmdk'):
                    vmdk_path = os.path.join(vm_path, file)
                    parent_hint = check_vmdk_parent_hint(vmdk_path)
                    
                    if parent_hint and parent_hint == snapshot_disk_file:
                        associated_vms.append(vm_name)
                        logger.info(f"发现关联: 快照文件 {snapshot_disk_file} 与虚拟机 {vm_name} 关联")
                        break
    
    except Exception as e:
        logger.error(f"检查快照vmdk关联失败: {str(e)}")
    
    return associated_vms

import subprocess

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
            
            # 如果还是找不到，尝试查找最新的.vmx文件（按修改时间排序）
            vmx_files = []
            for root, dirs, files in os.walk(vm_dir):
                for file in files:
                    if file.endswith('.vmx'):
                        file_path = os.path.join(root, file)
                        try:
                            mtime = os.path.getmtime(file_path)
                            vmx_files.append((file_path, mtime))
                        except:
                            continue
            
            if vmx_files:
                # 按修改时间降序排序，返回最新的
                vmx_files.sort(key=lambda x: x[1], reverse=True)
                logger.info(f"未找到精确匹配的虚拟机文件，使用最新的: {vmx_files[0][0]}")
                return vmx_files[0][0]
        
        return None
        
    except Exception as e:
        logger.error(f"查找虚拟机文件失败: {str(e)}")
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

def get_vm_ip(vm_name):
    """获取虚拟机IP地址，优先用vmrun getGuestIPAddress"""
    try:
        # 1. 通过vmrun getGuestIPAddress
        vm_file = find_vm_file(vm_name)
        if vm_file:
            vmrun_path_exe = get_vmrun_path()
            
            if os.path.exists(vmrun_path_exe):
                try:
                    cmd = [vmrun_path_exe, 'getGuestIPAddress', vm_file, '-wait']
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
                logger.warning(f"vmrun路径不存在: {vmrun_path_exe}")
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
        
        logger.warning(f"无法获取虚拟机 {vm_name} 的IP地址")
        return None
    except Exception as e:
        logger.error(f"获取虚拟机IP失败: {str(e)}")
        return None

def get_vm_ip_from_template(vm_name):
    """从template_dir目录获取虚拟机IP地址"""
    try:
        # 使用template_dir目录
        vm_file = find_vm_file_in_template(vm_name)
        if not vm_file:
            logger.error(f"未找到虚拟机文件: {vm_name}")
            return None
        
        logger.info(f"找到虚拟机文件: {vm_file}")
        
        # 获取vmrun路径
        vmrun_path = get_vmrun_path()
        if not vmrun_path:
            logger.error("未找到vmrun路径")
            return None
        
        # 使用vmrun获取IP地址
        cmd = [vmrun_path, "getGuestIPAddress", vm_file]
      #  logger.info(f"执行命令: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            ip = result.stdout.strip()
            if is_valid_ip(ip):
                logger.info(f"获取到虚拟机IP: {ip}")
                return ip
            else:
                logger.error(f"获取到无效IP: {ip}")
                return None
        else:
            #logger.error(f"获取IP失败: {result.stderr}")
            return None
            
    except Exception as e:
        logger.error(f"获取虚拟机IP时发生错误: {str(e)}")
        return None

def find_vm_file_in_template(vm_name):
    """在template_dir目录中查找虚拟机文件"""
    try:
        # 使用template_dir目录
        search_dir = template_dir
        logger.info(f"在目录中搜索虚拟机文件: {search_dir}")
        
        if not os.path.exists(search_dir):
            logger.error(f"目录不存在: {search_dir}")
            return None
        
        # 精确匹配
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if file.endswith('.vmx'):
                    file_name_without_ext = os.path.splitext(file)[0]
                    if file_name_without_ext == vm_name:
                        vm_file_path = os.path.join(root, file)
                        logger.info(f"精确匹配找到虚拟机文件: {vm_file_path}")
                        return vm_file_path
        
        # 模糊匹配（大小写不敏感）
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if file.endswith('.vmx'):
                    file_name_without_ext = os.path.splitext(file)[0]
                    if vm_name.lower() in file_name_without_ext.lower():
                        vm_file_path = os.path.join(root, file)
                        logger.info(f"模糊匹配找到虚拟机文件: {vm_file_path}")
                        return vm_file_path
        
        # 兜底策略：返回最新修改的.vmx文件
        latest_file = None
        latest_time = 0
        
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if file.endswith('.vmx'):
                    file_path = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(file_path)
                        if mtime > latest_time:
                            latest_time = mtime
                            latest_file = file_path
                    except OSError:
                        continue
        
        if latest_file:
            logger.info(f"兜底策略找到最新虚拟机文件: {latest_file}")
            return latest_file
        
        logger.error(f"未找到虚拟机文件: {vm_name}")
        return None
        
    except Exception as e:
        logger.error(f"查找虚拟机文件时发生错误: {str(e)}")
        return None

@mupan_bp.route('/api/check-ssh-trust', methods=['POST'])
def check_ssh_trust():
    """检查SSH互信状态API"""
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        use_template_dir = data.get('use_template_dir', False)
        
        if not vm_name:
            return jsonify({
                'success': False,
                'message': '虚拟机名称不能为空'
            })
        
        logger.info(f"检查虚拟机 {vm_name} 的SSH互信状态")
        
        # 获取虚拟机IP
        if use_template_dir:
            vm_ip = get_vm_ip_from_template(vm_name)
        else:
            vm_ip = get_vm_ip(vm_name)
            
        if not vm_ip:
            return jsonify({
                'success': False,
                'trusted': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址'
            })
        
        logger.info(f"虚拟机 {vm_name} 的IP地址: {vm_ip}")
        
        # 检查SSH互信状态
        from app.utils.ssh_utils import check_ssh_trust_status
        trusted = check_ssh_trust_status(vm_ip, vm_username)
        
        return jsonify({
            'success': True,
            'trusted': trusted,
            'message': f'SSH互信状态: {"已互信" if trusted else "未互信"}',
            'vm_ip': vm_ip
        })
            
    except Exception as e:
        logger.error(f"检查SSH互信状态时发生错误: {str(e)}")
        return jsonify({
            'success': False,
            'trusted': False,
            'message': f'检查SSH互信状态时发生错误: {str(e)}'
        })

@mupan_bp.route('/api/setup-trust', methods=['POST'])
def setup_trust():
    """设置SSH互信API"""
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        use_template_dir = data.get('use_template_dir', False)
        
        if not vm_name:
            return jsonify({
                'success': False,
                'message': '虚拟机名称不能为空'
            })
        
        logger.info(f"开始为虚拟机 {vm_name} 设置SSH互信")
        
        # 获取虚拟机IP
        if use_template_dir:
            vm_ip = get_vm_ip_from_template(vm_name)
        else:
            vm_ip = get_vm_ip(vm_name)
            
        if not vm_ip:
            return jsonify({
                'success': False,
                'message': f'无法获取虚拟机 {vm_name} 的IP地址'
            })
        
        logger.info(f"虚拟机 {vm_name} 的IP地址: {vm_ip}")
        
        # 设置SSH互信
        success, message = setup_ssh_trust(vm_ip, vm_username, vm_password)
        
        if success:
            logger.info(f"虚拟机 {vm_name} SSH互信设置成功")
            return jsonify({
                'success': True,
                'message': f'SSH互信设置成功，虚拟机IP: {vm_ip}'
            })
        else:
            logger.error(f"虚拟机 {vm_name} SSH互信设置失败: {message}")
            return jsonify({
                'success': False,
                'message': f'SSH互信设置失败: {message}'
            })
            
    except Exception as e:
        logger.error(f"设置SSH互信时发生错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'设置SSH互信时发生错误: {str(e)}'
        })