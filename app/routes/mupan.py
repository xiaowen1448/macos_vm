import os
import re
import json
from datetime import datetime
from flask import Blueprint, request, jsonify
import logging
from config import *
# 创建蓝图
mupan_bp = Blueprint('mupan', __name__)

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

# 配置日志
logger = logging.getLogger(__name__)

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