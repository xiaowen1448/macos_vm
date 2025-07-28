import json
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from functools import wraps
import os
import datetime
import uuid
import threading
import time
import subprocess
import paramiko

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('app_debug.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # 用于会话加密

# 固定账号
USERNAME = 'admin'
PASSWORD = '123456'

#模板虚拟机路径
template_dir = r'D:\macos_vm\TemplateVM\macos10.12'

# 全局任务存储
clone_tasks = {}

# 确保 web/templates/ 目录下有 login.html 和 dashboard.html 文件，否则会报错。
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    logger.debug("登录页面访问")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        logger.debug(f"用户尝试登录: {username}")
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            logger.info(f"用户 {username} 登录成功")
            return redirect(url_for('clone_vm_page'))
        else:
            logger.warning(f"用户 {username} 登录失败")
            flash('用户名或密码错误')
    return render_template('login.html')
    
@app.route('/dashboard')
@login_required
def dashboard():
    logger.debug("访问dashboard页面")
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
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y/%m/%d %H:%M')
                size = stat.st_size
                script_list.append({'name': fname, 'mtime': mtime, 'size': size})
                logger.debug(f"找到脚本文件: {fname}, 大小: {size} bytes")
    script_list.sort(key=lambda x: x['name'])
    
    logger.info(f"Dashboard数据准备完成 - 成品VM: {len(vm_list)}, 临时VM: {len(vm_data)}, 脚本: {len(script_list)}")
    return render_template('dashboard.html', username=session.get('username'), vm_list=vm_list,vm_data=vm_data, script_list=script_list, wuma_list=wuma_list)

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
    
    # 获取配置文件目录列表
    plist_dirs = []
    base_plist_dir = r'D:\macos_vm\plist'
    
    if os.path.exists(base_plist_dir):
        for item in os.listdir(base_plist_dir):
            item_path = os.path.join(base_plist_dir, item)
            if os.path.isdir(item_path):
                # 计算目录中的plist文件数量
                plist_count = 0
                for fname in os.listdir(item_path):
                    if fname.endswith('.plist') or fname.endswith('.txt'):
                        plist_count += 1
                
                plist_dirs.append({
                    'name': item,
                    'path': item_path,
                    'count': plist_count
                })
    
    return render_template('clone_vm.html', 
                         template_vms=template_vms, 
                         plist_dirs=plist_dirs)

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
        
        # 批量获取运行中的虚拟机列表
        running_vms = set()
        try:
            vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
            if not os.path.exists(vmrun_path):
                vmrun_path = r'C:\Program Files\VMware\VMware Workstation\vmrun.exe'
            
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
                            create_time = datetime.datetime.fromtimestamp(os.path.getmtime(vm_path))
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

@app.route('/vm_trust')
@login_required
def vm_trust_page():
    """虚拟机互信管理页面"""
    return render_template('vm_trust.html')

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
        
        # 验证plist文件数量
        plist_dir = data.get('configPlist')
        clone_count = int(data.get('cloneCount'))
        
        logger.debug(f"plist目录: {plist_dir}")
        logger.debug(f"克隆数量: {clone_count}")
        logger.debug(f"plist目录是否存在: {os.path.exists(plist_dir)}")
        
        if os.path.exists(plist_dir):
            plist_files = []
            for fname in os.listdir(plist_dir):
                if fname.endswith('.plist') or fname.endswith('.txt'):
                    plist_files.append(fname)
            
            logger.debug(f"找到plist文件数量: {len(plist_files)}")
            
            if len(plist_files) < clone_count:
                logger.warning(f"plist文件不足: 需要{clone_count}个，只有{len(plist_files)}个")
                return jsonify({
                    'success': False, 
                    'message': f'plist文件不足：目录中有 {len(plist_files)} 个文件，但需要克隆 {clone_count} 个虚拟机。请增加plist文件或减少克隆数量。'
                })
        else:
            logger.error(f"plist目录不存在: {plist_dir}")
            return jsonify({'success': False, 'message': f'配置文件目录不存在: {plist_dir}'})
        
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
            'start_time': datetime.datetime.now(),
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
        template_path = os.path.join(template_dir, params['templateVM'])
        print(f"[DEBUG] 模板路径: {template_path}")
        print(f"[DEBUG] 模板路径是否存在: {os.path.exists(template_path)}")
        
        if not os.path.exists(template_path):
            add_task_log(task_id, 'error', f'模板虚拟机不存在: {template_path}')
            print(f"[DEBUG] 错误：模板虚拟机不存在: {template_path}")
            task['status'] = 'failed'
            return
        
        # 确保目标目录存在
        target_dir = params['targetDir']
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
            
            vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
            if not os.path.exists(vmrun_path):
                vmrun_path = r'C:\Program Files\VMware\VMware Workstation\vmrun.exe'
            
            print(f"[DEBUG] vmrun路径: {vmrun_path}")
            print(f"[DEBUG] vmrun是否存在: {os.path.exists(vmrun_path)}")
            
            # 生成快照名称
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
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
            add_task_log(task_id, 'info', f'执行快照命令: {" ".join(snapshot_cmd)}')
            
            try:
                # 执行快照命令
                print(f"[DEBUG] 开始执行快照命令...")
                result = subprocess.run(snapshot_cmd, capture_output=True, text=True, timeout=120)
                
                print(f"[DEBUG] 快照命令返回码: {result.returncode}")
                print(f"[DEBUG] 快照命令输出: {result.stdout}")
                if result.stderr:
                    print(f"[DEBUG] 快照命令错误: {result.stderr}")
                
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
        
        # 获取plist文件列表
        plist_dir = params.get('configPlist')
        plist_files = []
        print(f"[DEBUG] plist目录: {plist_dir}")
        print(f"[DEBUG] plist目录是否存在: {os.path.exists(plist_dir)}")
        
        if os.path.exists(plist_dir):
            for fname in os.listdir(plist_dir):
                if fname.endswith('.plist') or fname.endswith('.txt'):
                    plist_files.append(fname)
        
        print(f"[DEBUG] 找到plist文件数量: {len(plist_files)}")
        print(f"[DEBUG] plist文件列表: {plist_files}")
        
        # 开始克隆
        clone_count = int(params['cloneCount'])
        print(f"[DEBUG] 开始克隆，总数: {clone_count}")
        
        add_task_log(task_id, 'info', f'找到 {len(plist_files)} 个plist文件，需要克隆 {clone_count} 个虚拟机')
        
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
                
                # 生成虚拟机名称和文件夹名称
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
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
                
                # 分配plist文件
                plist_file = plist_files[i % len(plist_files)] if plist_files else None
                print(f"[DEBUG] 分配的plist文件: {plist_file}")
                
                add_task_log(task_id, 'info', f'开始克隆第 {i+1}/{clone_count} 个虚拟机: {vm_name}')
                add_task_log(task_id, 'info', f'虚拟机文件夹: {vm_folder_path}')
                if plist_file:
                    add_task_log(task_id, 'info', f'使用配置文件: {plist_file}')
                
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
                vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
                if not os.path.exists(vmrun_path):
                    vmrun_path = r'C:\Program Files\VMware\VMware Workstation\vmrun.exe'
                
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
                add_task_log(task_id, 'info', f'执行命令: {" ".join(clone_cmd)}')
                
                # 执行克隆
                print(f"[DEBUG] 开始执行克隆命令...")
                result = subprocess.run(clone_cmd, capture_output=True, text=True, timeout=300)
                
                print(f"[DEBUG] 克隆命令返回码: {result.returncode}")
                print(f"[DEBUG] 克隆命令输出: {result.stdout}")
                if result.stderr:
                    print(f"[DEBUG] 克隆命令错误: {result.stderr}")
                
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
                    
                    # 如果配置了自动启动
                    if params.get('autoStart') == 'true':
                        start_cmd = [vmrun_path, 'start', vm_file_path]
                        subprocess.run(start_cmd, capture_output=True, text=True)
                        add_task_log(task_id, 'info', f'虚拟机 {vm_name} 已启动')
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
            'timestamp': datetime.datetime.now().isoformat(),
            'level': level,
            'message': message
        }
        task['logs'].append(log_entry)

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
            
            while task['status'] in ['running'] and timeout_counter < max_timeout:
                # 发送新日志和进度数据
                while last_log_index < len(task['logs']):
                    log_entry = task['logs'][last_log_index]
                    
                    # 检查是否是进度数据
                    if isinstance(log_entry, dict) and log_entry.get('type') == 'progress':
                        # 发送进度数据
                        yield f"data: {json.dumps(log_entry)}\n\n"
                    else:
                        # 发送普通日志
                        log_data = {
                            'type': 'log',
                            'level': log_entry['level'],
                            'message': log_entry['message']
                        }
                        yield f"data: {json.dumps(log_data)}\n\n"
                    
                    last_log_index += 1
                
                # 发送统计更新
                stats_data = {
                    'type': 'stats',
                    'stats': task['stats']
                }
                yield f"data: {json.dumps(stats_data)}\n\n"
                
                timeout_counter += 1
                time.sleep(1)
            
            # 发送完成信号
            complete_data = {
                'type': 'complete',
                'success': task['status'] == 'completed',
                'stats': task['stats']
            }
            yield f"data: {json.dumps(complete_data)}\n\n"
            
        except Exception as e:
            print(f"[DEBUG] 日志流生成错误: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'日志流错误: {str(e)}'})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

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
            vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
            if not os.path.exists(vmrun_path):
                vmrun_path = r'C:\Program Files\VMware\VMware Workstation\vmrun.exe'
            
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
        vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
        if not os.path.exists(vmrun_path):
            vmrun_path = r'C:\Program Files\VMware\VMware Workstation\vmrun.exe'
        
        start_cmd = [vmrun_path, 'start', vm_file]
        result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': '虚拟机启动成功'})
        else:
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
        vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
        if not os.path.exists(vmrun_path):
            vmrun_path = r'C:\Program Files\VMware\VMware Workstation\vmrun.exe'
        
        stop_cmd = [vmrun_path, 'stop', vm_file, 'hard']
        result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': '虚拟机停止成功'})
        else:
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
        vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
        if not os.path.exists(vmrun_path):
            vmrun_path = r'C:\Program Files\VMware\VMware Workstation\vmrun.exe'
        
        # 先停止虚拟机
        stop_cmd = [vmrun_path, 'stop', vm_file, 'hard']
        stop_result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=60)
        
        # 等待一下再启动
        import time
        time.sleep(2)
        
        # 启动虚拟机
        start_cmd = [vmrun_path, 'start', vm_file]
        start_result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=60)
        
        if start_result.returncode == 0:
            return jsonify({'success': True, 'message': '虚拟机重启成功'})
        else:
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
                vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
                if not os.path.exists(vmrun_path):
                    vmrun_path = r'C:\Program Files\VMware\VMware Workstation\vmrun.exe'
                
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
        vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
        if not os.path.exists(vmrun_path):
            vmrun_path = r'C:\Program Files\VMware\VMware Workstation\vmrun.exe'
        
        list_cmd = [vmrun_path, 'list']
        result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            running_vms = result.stdout.strip().split('\n')[1:]  # 跳过标题行
            vm_name = os.path.splitext(os.path.basename(vm_path))[0]
            
            for vm in running_vms:
                if vm.strip() and vm_name in vm:
                    return 'running'
        
        return 'stopped'
        
    except Exception as e:
        print(f"[DEBUG] 获取虚拟机状态失败: {str(e)}")
        return 'unknown'

def get_vm_ip(vm_name):
    """获取虚拟机IP地址，优先用vmrun getGuestIPAddress"""
    logger.debug(f"开始获取虚拟机 {vm_name} 的IP地址")
    try:
        # 1. 通过vmrun getGuestIPAddress
        vm_file = find_vm_file(vm_name)
        if vm_file:
            logger.debug(f"找到虚拟机文件: {vm_file}")
            vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
            if not os.path.exists(vmrun_path):
                vmrun_path = r'C:\Program Files\VMware\VMware Workstation\vmrun.exe'
                logger.debug(f"使用备用vmrun路径: {vmrun_path}")
            
            if os.path.exists(vmrun_path):
                try:
                    cmd = [vmrun_path, 'getGuestIPAddress', vm_file, '-wait']
                    logger.debug(f"执行vmrun命令: {cmd}")
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        ip = result.stdout.strip()
                        logger.debug(f"vmrun返回IP: {ip}")
                        if is_valid_ip(ip):
                            logger.info(f"通过vmrun成功获取IP: {ip}")
                            return ip
                        else:
                            logger.warning(f"vmrun返回的IP格式无效: {ip}")
                    else:
                        logger.warning(f"vmrun命令执行失败，返回码: {result.returncode}, 错误: {result.stderr}")
                except Exception as e:
                    logger.error(f"vmrun getGuestIPAddress 获取IP失败: {str(e)}")
            else:
                logger.warning(f"vmrun路径不存在: {vmrun_path}")
        else:
            logger.warning(f"未找到虚拟机文件: {vm_name}")
        
        # 2. 兜底：调用现有的IP获取脚本
        ip_script = os.path.join(os.path.dirname(__file__), '..', 'bat', 'get_vm_ip.bat')
        if os.path.exists(ip_script):
            logger.debug(f"尝试使用IP获取脚本: {ip_script}")
            try:
                result = subprocess.run([ip_script, vm_name], capture_output=True, text=True, timeout=30)
                if result.returncode == 0 and result.stdout.strip():
                    ip = result.stdout.strip()
                    logger.debug(f"脚本返回IP: {ip}")
                    if is_valid_ip(ip):
                        logger.info(f"通过脚本成功获取IP: {ip}")
                        return ip
                    else:
                        logger.warning(f"脚本返回的IP格式无效: {ip}")
                else:
                    logger.warning(f"IP获取脚本执行失败，返回码: {result.returncode}")
            except Exception as e:
                logger.error(f"IP获取脚本执行异常: {str(e)}")
        else:
            logger.debug(f"IP获取脚本不存在: {ip_script}")
        
        # 3. 兜底：从VMX文件读取
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

def check_ssh_trust_status(ip, username='wx'):
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
    """获取虚拟机在线状态（严格校验：IP获取成功 + SSH端口开放 + SSH互信成功）"""
    logger.debug(f"检查虚拟机 {vm_name} 的在线状态（严格校验）")
    
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
                'ssh_port_open': False
            }
        
        vm_status = get_vm_status(vm_file)
        if vm_status != 'running':
            logger.debug(f"虚拟机 {vm_name} 未运行，状态: {vm_status}")
            return {
                'status': 'offline',
                'reason': f'虚拟机未运行 ({vm_status})',
                'ip': None,
                'ssh_trust': False,
                'ssh_port_open': False
            }
        
        # 2. 获取IP地址（条件1：IP地址获取成功）
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            logger.debug(f"虚拟机 {vm_name} 无法获取IP地址")
            return {
                'status': 'offline',
                'reason': '无法获取IP地址',
                'ip': None,
                'ssh_trust': False,
                'ssh_port_open': False
            }
        
        logger.debug(f"虚拟机 {vm_name} IP地址获取成功: {vm_ip}")
        
        # 3. 检查IP连通性
        ip_status = check_ip_connectivity(vm_ip)
        if not ip_status['success']:
            logger.debug(f"虚拟机 {vm_name} IP {vm_ip} 不可达")
            return {
                'status': 'offline',
                'reason': f'IP不可达: {ip_status.get("error", "未知错误")}',
                'ip': vm_ip,
                'ssh_trust': False,
                'ssh_port_open': False
            }
        
        # 4. 检查SSH端口是否开放（条件2：SSH端口开放）
        ssh_port_open = check_ssh_port_open(vm_ip)
        if not ssh_port_open:
            logger.debug(f"虚拟机 {vm_name} SSH端口未开放")
            return {
                'status': 'partial',
                'reason': 'IP可达但SSH端口未开放',
                'ip': vm_ip,
                'ssh_trust': False,
                'ssh_port_open': False
            }
        
        logger.debug(f"虚拟机 {vm_name} SSH端口开放")
        
        # 5. 检查SSH互信状态（条件3：SSH已添加互信可以成功登录）
        ssh_trust_status = check_ssh_trust_status(vm_ip)
        
        if ssh_trust_status:
            logger.info(f"虚拟机 {vm_name} 完全在线：IP可达 + SSH端口开放 + SSH互信成功")
            return {
                'status': 'online',
                'reason': 'IP可达 + SSH端口开放 + SSH互信成功',
                'ip': vm_ip,
                'ssh_trust': True,
                'ssh_port_open': True
            }
        else:
            logger.debug(f"虚拟机 {vm_name} IP可达且SSH端口开放，但SSH互信未设置")
            return {
                'status': 'offline',
                'reason': 'IP可达且SSH端口开放，但SSH互信未设置',
                'ip': vm_ip,
                'ssh_trust': False,
                'ssh_port_open': True
            }
            
    except Exception as e:
        logger.error(f"检查虚拟机 {vm_name} 在线状态时出错: {str(e)}")
        return {
            'status': 'error',
            'reason': f'检查状态时出错: {str(e)}',
            'ip': None,
            'ssh_trust': False,
            'ssh_port_open': False
        }

def find_vm_file(vm_name):
    """查找虚拟机文件"""
    vm_dir = r'D:\macos_vm\NewVM'
    if os.path.exists(vm_dir):
        for root, dirs, files in os.walk(vm_dir):
            for file in files:
                if file.endswith('.vmx') and vm_name in file:
                    return os.path.join(root, file)
    return None

def get_vm_snapshots(vm_path):
    """获取虚拟机快照列表"""
    try:
        vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
        if not os.path.exists(vmrun_path):
            vmrun_path = r'C:\Program Files\VMware\VMware Workstation\vmrun.exe'
        
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
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/ssh_trust', methods=['POST'])
@login_required
def api_ssh_trust():
    """设置SSH互信"""
    logger.info("收到SSH互信设置API请求")
    try:
        data = request.get_json()
        vm_name = data.get('vm_name')
        username = data.get('username', 'wx')
        password = data.get('password', '123456')
        
        logger.debug(f"SSH互信参数 - 虚拟机: {vm_name}, 用户: {username}")
        
        if not vm_name:
            logger.warning("虚拟机名称不能为空")
            return jsonify({'success': False, 'message': '虚拟机名称不能为空'})
        
        logger.info(f"开始为虚拟机 {vm_name} 设置SSH互信")
        
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)