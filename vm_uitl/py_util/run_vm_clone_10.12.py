import os
import sys
import subprocess
from glob import glob
from flask import request, jsonify

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *

def log(msg):
    print(f"[INFO] {msg}")

def error(msg):
    print(f"[ERROR] {msg}")
    sys.exit(1)

def select_template(template_base_dir):
    templates = glob(os.path.join(template_base_dir, "*.vmx"))
    if not templates:
        error(f"模板目录 {template_base_dir} 下未找到任何 .vmx 文件！")
    print("可用模板：")
    for idx, t in enumerate(templates, 1):
        print(f"  {idx}. {t}")
    idx = input(f"请选择模板序号 (1-{len(templates)}，默认1): ").strip()
    idx = int(idx) if idx.isdigit() and 1 <= int(idx) <= len(templates) else 1
    return templates[idx-1]

def check_template_complete(template_vmx):
    template_dir = os.path.dirname(template_vmx)
    vmx_exists = any(f.endswith('.vmx') for f in os.listdir(template_dir))
    vmdk_exists = any(f.endswith('.vmdk') for f in os.listdir(template_dir))
    if not vmx_exists or not vmdk_exists:
        error("模板虚拟机目录不完整，必须包含 .vmx 文件和至少一个 .vmdk 文件！")
    log("模板虚拟机完整。")

@app.route('/api/clone_vm', methods=['POST'])
def api_clone_vm():
    data = request.form
    # 获取参数并做健壮处理
    clone_count = int(data.get('clone_count', 3))
    base_name = data.get('base_name', 'vm_clone_')
    target_dir = data.get('target_dir', clone_dir)  # 使用全局配置
    template_vmx = data.get('template_vmx')
    clone_type = data.get('clone_type', 'full')
    inc_type = data.get('inc_type', 'num')  # 'num' or 'alpha'
    print(f'clone_count: {clone_count}')
    print(f'base_name: {base_name}')
    print(f'target_dir: {target_dir}')
    print(f'template_vmx: {template_vmx}')
    print(f'clone_type: {clone_type}')
    print(f'inc_type: {inc_type}')
    # # 检查参数
    # if not template_vmx or not os.path.exists(template_vmx):
    #     return jsonify({'status': 'error', 'msg': '模板虚拟机不存在！'}), 400

    # # 生成虚拟机名称
    # names = []
    # if inc_type == 'num':
    #     for i in range(1, clone_count + 1):
    #         names.append(f"{base_name}{i:02d}")
    # else:  # alpha
    #     for i in range(clone_count):
    #         suffix = chr(ord('A') + i)
    #         names.append(f"{base_name}{suffix}")

    # # 克隆
    # vmrun_path = r'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
    # new_vm_paths = []
    # for name in names:
    #     clone_dir = os.path.join(target_dir, name)
    #     os.makedirs(clone_dir, exist_ok=True)
    #     clone_vmx = os.path.join(clone_dir, f"{name}.vmx")
    #     cmd = [
    #         vmrun_path,
    #         'clone',
    #         template_vmx,
    #         clone_vmx,
    #         clone_type,
    #         '-cloneName=' + name
    #     ]
    #     try:
    #         subprocess.run(cmd, check=True)
    #         new_vm_paths.append(clone_vmx)
    #     except Exception as e:
    #         return jsonify({'status': 'error', 'msg': f'克隆失败: {e}'})
    # return jsonify({'status': 'ok', 'cloned': new_vm_paths})

if __name__ == '__main__':
    app.run(debug=True)