import json
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from functools import wraps
import os
import datetime
import uuid
import threading
import time
import subprocess

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
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误')
    return render_template('login.html')
    
@app.route('/dashboard')
@login_required
def dashboard():
    #获取虚拟机名称
    vm_temp_dir = r'D:\macos_vm\NewVM\10.12'
    vm_chengpin_dir = r'D:\macos_vm\NewVM\chengpin_vm'
    vms = []
    vm_data=[]
    for root, dirs, files in os.walk(vm_chengpin_dir):
        for fname in files:
            if fname.endswith('.vmx'):
                vms.append({
                    'name': fname,
                    'ip':'未获取到',
                    'status': '已关闭',
                    'imessage': '未知'
                    })
                #{'name': fname,'ip': '未获取到'，'status': '已关闭'，'imessage': '未知'}
    

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
    if os.path.exists(script_dir):
        for fname in os.listdir(script_dir):
            fpath = os.path.join(script_dir, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y/%m/%d %H:%M')
                size = stat.st_size
                script_list.append({'name': fname, 'mtime': mtime, 'size': size})
    script_list.sort(key=lambda x: x['name'])
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
    try:
        data = request.get_json()
        print(f"[DEBUG] API收到克隆请求: {data}")
        
        # 验证必要参数
        required_fields = ['templateVM', 'cloneCount', 'targetDir', 'namingPattern', 'configPlist']
        for field in required_fields:
            if not data.get(field):
                print(f"[DEBUG] 缺少必要参数: {field}")
                return jsonify({'success': False, 'message': f'缺少必要参数: {field}'})
        
        # 验证plist文件数量
        plist_dir = data.get('configPlist')
        clone_count = int(data.get('cloneCount'))
        
        print(f"[DEBUG] plist目录: {plist_dir}")
        print(f"[DEBUG] 克隆数量: {clone_count}")
        print(f"[DEBUG] plist目录是否存在: {os.path.exists(plist_dir)}")
        
        if os.path.exists(plist_dir):
            plist_files = []
            for fname in os.listdir(plist_dir):
                if fname.endswith('.plist') or fname.endswith('.txt'):
                    plist_files.append(fname)
            
            print(f"[DEBUG] 找到plist文件数量: {len(plist_files)}")
            
            if len(plist_files) < clone_count:
                print(f"[DEBUG] plist文件不足: 需要{clone_count}个，只有{len(plist_files)}个")
                return jsonify({
                    'success': False, 
                    'message': f'plist文件不足：目录中有 {len(plist_files)} 个文件，但需要克隆 {clone_count} 个虚拟机。请增加plist文件或减少克隆数量。'
                })
        else:
            print(f"[DEBUG] plist目录不存在: {plist_dir}")
            return jsonify({'success': False, 'message': f'配置文件目录不存在: {plist_dir}'})
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        print(f"[DEBUG] 生成任务ID: {task_id}")
        
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
        print(f"[DEBUG] 任务已创建并存储")
        
        # 启动克隆线程
        thread = threading.Thread(target=clone_vm_worker, args=(task_id,))
        thread.daemon = True
        thread.start()
        print(f"[DEBUG] 克隆线程已启动")
        
        return jsonify({'success': True, 'task_id': task_id})
        
    except Exception as e:
        print(f"[DEBUG] API异常: {str(e)}")
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
        if task_id not in clone_tasks:
            yield f"data: {json.dumps({'type': 'error', 'message': '任务不存在'})}\n\n"
            return
        
        task = clone_tasks[task_id]
        last_log_index = 0
        
        while task['status'] in ['running']:
            # 发送新日志
            while last_log_index < len(task['logs']):
                log_entry = task['logs'][last_log_index]
                log_data = {
                    'type': 'log',
                    'level': log_entry['level'],
                    'message': log_entry['message']
                }
                yield f"data: {json.dumps(log_data)}\n\n"
                last_log_index += 1
            
            # 发送进度更新
            progress_data = {
                'type': 'progress',
                'current': task['progress']['current'],
                'total': task['progress']['total']
            }
            yield f"data: {json.dumps(progress_data)}\n\n"
            
            # 发送统计更新
            stats_data = {
                'type': 'stats',
                'stats': task['stats']
            }
            yield f"data: {json.dumps(stats_data)}\n\n"
            
            time.sleep(1)
        
        # 发送完成信号
        complete_data = {
            'type': 'complete',
            'success': task['status'] == 'completed',
            'stats': task['stats']
        }
        yield f"data: {json.dumps(complete_data)}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/vm_list')
@login_required
def api_vm_list():
    """获取虚拟机列表"""
    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        
        # 扫描虚拟机目录
        vm_dir = r'D:\macos_vm\NewVM'
        vms = []
        stats = {'total': 0, 'running': 0, 'stopped': 0, 'online': 0}
        
        if os.path.exists(vm_dir):
            for root, dirs, files in os.walk(vm_dir):
                for file in files:
                    if file.endswith('.vmx'):
                        vm_path = os.path.join(root, file)
                        vm_name = os.path.splitext(file)[0]
                        
                        # 获取虚拟机状态
                        vm_status = get_vm_status(vm_path)
                        
                        # 获取IP地址
                        vm_ip = get_vm_ip(vm_name)
                        
                        # 获取五码信息
                        wuma_info = get_wuma_info(vm_name)
                        
                        # 检查SSH连接状态
                        ssh_status = check_ssh_status(vm_ip) if vm_ip else 'offline'
                        
                        vm_info = {
                            'name': vm_name,
                            'path': vm_path,
                            'status': vm_status,
                            'ip': vm_ip,
                            'wuma_info': wuma_info,
                            'ssh_status': ssh_status
                        }
                        vms.append(vm_info)
                        
                        # 更新统计信息
                        stats['total'] += 1
                        if vm_status == 'running':
                            stats['running'] += 1
                        elif vm_status == 'stopped':
                            stats['stopped'] += 1
                        if ssh_status == 'online':
                            stats['online'] += 1
        
        # 计算分页
        total_count = len(vms)
        total_pages = (total_count + page_size - 1) // page_size
        start_index = (page - 1) * page_size
        end_index = min(start_index + page_size, total_count)
        
        # 分页数据
        paged_vms = vms[start_index:end_index] if vms else []
        
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
        print(f"[DEBUG] 获取虚拟机列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取虚拟机列表失败: {str(e)}'
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
    """获取虚拟机IP地址"""
    try:
        # 这里可以调用现有的IP获取脚本
        ip_script = os.path.join(os.path.dirname(__file__), '..', 'bat', 'get_vm_ip.bat')
        if os.path.exists(ip_script):
            result = subprocess.run([ip_script, vm_name], capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return result.stdout.strip()
        
        return None
        
    except Exception as e:
        print(f"[DEBUG] 获取虚拟机IP失败: {str(e)}")
        return None

def get_wuma_info(vm_name):
    """获取虚拟机五码信息"""
    try:
        # 这里可以从plist文件或其他地方获取五码信息
        # 暂时返回占位符
        return f"五码信息-{vm_name}"
        
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

if __name__ == '__main__':
    app.run(debug=True) 
   #dashboard()