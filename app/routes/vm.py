from flask import Blueprint, render_template
from functools import wraps
from app.utils.vm_utils import get_vm_list_from_directory
from config import *
from app.utils.vm_utils import get_wuma_info_generic, get_ju_info_generic, get_vm_online_status
# 导入日志工具
from app.utils.log_utils import get_logger

# 获取日志记录器
logger = get_logger(__name__)

# 创建虚拟机相关的蓝图
vm_bp = Blueprint('vm', __name__)

# 导入login_required装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 这里应该导入实际的login_required逻辑
        # 由于我们是从主应用移动过来，暂时保持简单
        return f(*args, **kwargs)
    return decorated_function


@vm_bp.route('/clone_vm')
@login_required
def clone_vm_page():
    """虚拟机克隆页面"""
    import os
    from config import template_dir, clone_dir, wuma_config_dir
    
    # 获取模板虚拟机列表（递归查找子目录，只显示文件名）
    template_vms = []
    if os.path.exists(template_dir):
        for root, dirs, files in os.walk(template_dir):
            for file in files:
                if file.endswith('.vmx'):
                    # 只提取文件名（不包含扩展名）作为显示名称
                    file_name = os.path.splitext(file)[0]
                    template_vms.append({'name': file_name})
    
    # 获取五码配置文件列表
    configs = []
    if os.path.exists(wuma_config_dir):
        for file in os.listdir(wuma_config_dir):
            file_path = os.path.join(wuma_config_dir, file)
            if os.path.isfile(file_path) and file.endswith('.txt'):
                # 计算可用五码数量
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    available_count = 0
                    for line in lines:
                        line = line.strip()
                        if line and line.startswith(':') and line.endswith(':') and len(line.split(':')) == 7:
                            available_count += 1
                    configs.append({
                        'path': file_path,
                        'display_name': file,
                        'available_count': available_count
                    })
                except Exception:
                    configs.append({
                        'path': file_path,
                        'display_name': file,
                        'available_count': 0
                    })
    
    return render_template('clone_vm.html', template_vms=template_vms, configs=configs, clone_dir=clone_dir)

# 虚拟机五码、母盘、ID管理页面
@vm_bp.route('/wuma')
@login_required
def wuma_page():
    """虚拟机五码管理页面"""
    return render_template('wuma.html')


@vm_bp.route('/mupan')
@login_required
def mupan_page():
    """虚拟机母盘管理页面"""
    return render_template('mupan.html')


@vm_bp.route('/id_management')
@login_required
def  id_management_page():
    """ID管理页面"""
    return render_template('id_management.html')

# 虚拟机脚本管理页面
@vm_bp.route('/vm_script')
@login_required
def vm_script_page():
    """虚拟机脚本管理页面"""
    return render_template('vm_script.html')

# 测试页面
@vm_bp.route('/test_mupan')
@login_required
def test_mupan_page():
    """母盘API测试页面"""
    return render_template('test_mupan_direct.html')

# 加密相关页面
@vm_bp.route('/encrypt_code')
@login_required
def encrypt_code_page():
    """代码加密页面"""
    return render_template('encrypt_code.html')


@vm_bp.route('/encrypt_wuma')
@login_required
def encrypt_wuma_page():
    """五码加密页面"""
    return render_template('encrypt_wuma.html')


@vm_bp.route('/encrypt_id')
@login_required
def encrypt_id_page():
    """id加密页面"""
    return render_template('encrypt_id.html')

# 代理IP分配页面
@vm_bp.route('/proxy_assign')
@login_required
def proxy_assign_page():
    """代理IP分配页面"""
    return render_template('proxy_assign.html')

# 系统相关页面
@vm_bp.route('/soft_version')
@login_required
def soft_version_page():
    """版本查看页面"""
    return render_template('soft_version.html')


@vm_bp.route('/vm_script_send')
@login_required
def vm_script_send_page():
    """发送脚本页面"""
    logger.debug("访问发送脚本页面")
    return render_template('vm_script_send.html')


@vm_bp.route('/soft_env')
@login_required
def soft_env_page():
    """环境变量页面"""
    return render_template('soft_env.html')

# 客户端管理页面
@vm_bp.route('/client_management')
@login_required
def client_management_page():
    """客户端管理页面"""
    return render_template('client_management.html')

# JSON解析页面
@vm_bp.route('/json_parser')
@login_required
def json_parser_page():
    """JSON解析功能页面"""
    return render_template('json_parser.html')

# 批量IM状态页面
@vm_bp.route('/batch_im_status')
@login_required
def batch_im_status_page():
    """批量IM状态管理页面"""
    return render_template('batch_im_status.html')

# 虚拟机信息页面
@vm_bp.route('/vm_info')
@login_required
def vm_info_page():
    """虚拟机成品信息页面"""
    return render_template('vm_info.html')

# 手机号管理页面
@vm_bp.route('/phone_management')
@login_required
def phone_management_page():
    """手机号管理页面"""
    return render_template('phone_management.html')

@vm_bp.route('/vm_icloud')
@login_required
def vm_icloud():
    return render_template('vm_icloud.html')

@vm_bp.route('/proxy_assign')
@login_required
def proxy_assign():
    return render_template('proxy_assign.html')

@vm_bp.route('/mass_messaging')
@login_required
def mass_messaging_page():
    return render_template('mass_messaging.html')

@vm_bp.route('/vm_management')
@login_required
def vm_management_page():
    """虚拟机信息管理页面"""
    return render_template('vm_management.html')




@vm_bp.route('/api/vm_chengpin_list')
@login_required
def api_vm_chengpin_list():
    """获取成品虚拟机列表"""
    return get_vm_list_from_directory(VM_DIRS['chengpin'], '成品虚拟机')


@vm_bp.route('/api/get_chengpin_wuma_info', methods=['POST'])
@login_required
def api_get_chengpin_wuma_info():
    """获取成品虚拟机五码信息"""
    return get_wuma_info_generic('成品虚拟机')


@vm_bp.route('/api/get_chengpin_ju_info', methods=['POST'])
@login_required
def api_get_chengpin_ju_info():
    """获取成品虚拟机JU值信息"""
    return get_ju_info_generic('成品虚拟机')




# 虚拟机目录配置
VM_DIRS = {
    '10_12': clone_dir,
    'chengpin': vm_chengpin_dir
}


@vm_bp.route('/api/vm_10_12_list')
@login_required
def api_vm_10_12_list():
    """获取10.12目录虚拟机列表"""
    return get_vm_list_from_directory(VM_DIRS['10_12'], '10.12目录')


@vm_bp.route('/api/get_10_12_wuma_info', methods=['POST'])
@login_required
def api_get_10_12_wuma_info():
    """获取10.12目录虚拟机五码信息"""
    return get_wuma_info_generic('10.12目录')


@vm_bp.route('/api/get_10_12_ju_info', methods=['POST'])
@login_required
def api_get_10_12_ju_info():
    """获取10.12目录虚拟机JU值信息"""
    return get_ju_info_generic('10.12目录')
