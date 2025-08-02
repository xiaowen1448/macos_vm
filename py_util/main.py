#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import *

def print_hi(name):
    """示例函数"""
    print(f'Hi, {name}')
    print(f'项目根目录: {project_root}')
    print(f'模板虚拟机路径: {template_dir}')
    print(f'克隆目录: {clone_dir}')
    print(f'成品虚拟机目录: {vm_chengpin_dir}')
    print(f'vmrun路径: {vmrun_path}')

if __name__ == '__main__':
    print_hi('macOS VM Manager')
    print("全局配置已加载:")
    print(f"- 用户名: {USERNAME}")
    print(f"- 模板目录: {template_dir}")
    print(f"- 克隆目录: {clone_dir}")
    print(f"- vmrun路径: {vmrun_path}")
