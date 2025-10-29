import os
from datetime import datetime
from flask import Blueprint, render_template, session
from app.utils.common_utils import login_required
from app.utils.log_utils import logger
from config import vm_chengpin_dir, vm_temp_dir

# 创建dashboard蓝图 - 设置url_prefix为''，以便直接通过'dashboard'访问
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='')

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    # logger.info("访问dashboard页面")
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    vms = []
    vm_data = []

    logger.debug(f"扫描成品虚拟机目录: {vm_chengpin_dir}")
    for root, dirs, files in os.walk(vm_chengpin_dir):
        for fname in files:
            if fname.endswith('.vmx'):
                vms.append({
                    'name': fname,
                    'ip': '未获取到',
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
                # logger.debug(f"找到临时虚拟机: {fname2}")

    # 成品vm路径：D:\macos_vm\NewVM\10.12
    vm_list = vms
    # 临时克隆vm路径：D:\macos_vm\NewVM\chengpin_vm
    vm_data = vm_data
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
                # logger.debug(f"找到脚本文件: {fname}, 大小: {size} bytes")
    script_list.sort(key=lambda x: x['name'])

    #logger.info(f"Dashboard数据准备完成 - 成品VM: {len(vm_list)}, 临时VM: {len(vm_data)}, 脚本: {len(script_list)}")
    return render_template('dashboard.html', username=session.get('username'), vm_list=vm_list, vm_data=vm_data,
                           script_list=script_list, wuma_list=wuma_list, current_time=current_time)


