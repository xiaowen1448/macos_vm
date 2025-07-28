#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

def simple_test():
    """简单测试分页逻辑"""
    scripts_dir = r'D:\macos_vm\macos_sh'
    
    if os.path.exists(scripts_dir):
        # 获取所有.sh文件
        sh_files = [f for f in os.listdir(scripts_dir) if f.endswith('.sh')]
        sh_files.sort()
        
        print(f"总脚本数量: {len(sh_files)}")
        print(f"脚本列表: {sh_files}")
        
        # 测试分页大小5
        print("\n=== 分页大小5 ===")
        page_size = 5
        total_count = len(sh_files)
        total_pages = (total_count + page_size - 1) // page_size
        
        for page in range(1, total_pages + 1):
            start_index = (page - 1) * page_size
            end_index = min(start_index + page_size, total_count)
            current_page = sh_files[start_index:end_index]
            print(f"第{page}页: {current_page} (索引{start_index}-{end_index-1})")
        
        # 测试分页大小10
        print("\n=== 分页大小10 ===")
        page_size = 10
        total_pages = (total_count + page_size - 1) // page_size
        
        for page in range(1, total_pages + 1):
            start_index = (page - 1) * page_size
            end_index = min(start_index + page_size, total_count)
            current_page = sh_files[start_index:end_index]
            print(f"第{page}页: {current_page} (索引{start_index}-{end_index-1})")
    else:
        print(f"目录不存在: {scripts_dir}")

if __name__ == "__main__":
    simple_test() 