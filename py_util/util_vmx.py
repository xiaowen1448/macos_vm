import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *

def find_vmx_files(directory, str_file):
    """遍历目录及其子目录，查找所有 .vmx 文件"""
    vmx_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(str_file):
                vmx_files.append(os.path.join(root, file))
    return vmx_files

def read_vmx_files(directory):
    #传入包含vmx的文本
    vmx_files = []
    # 读取所有行到一个列表中
    with open(directory, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        for line in lines:
            clean_path = line.strip().strip('"\'')
           # print(clean_path)
            absolute_path = os.path.abspath(clean_path)
            vmx_files.append(absolute_path)
    return vmx_files

def get_default_vm_directories():
    """获取默认的虚拟机目录列表"""
    return {
        'template': template_dir,
        'clone': clone_dir,
        'chengpin': vm_chengpin_dir
    }