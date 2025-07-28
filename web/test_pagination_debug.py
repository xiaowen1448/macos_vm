#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import datetime

def test_pagination_logic():
    """测试分页逻辑"""
    scripts_dir = r'D:\macos_vm\macos_sh'
    scripts = []
    
    if os.path.exists(scripts_dir):
        print(f"扫描目录: {scripts_dir}")
        
        for filename in os.listdir(scripts_dir):
            if filename.endswith('.sh'):
                file_path = os.path.join(scripts_dir, filename)
                try:
                    # 获取文件信息
                    stat = os.stat(file_path)
                    size = stat.st_size
                    modified_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 格式化文件大小
                    if size < 1024:
                        size_str = f"{size}B"
                    elif size < 1024 * 1024:
                        size_str = f"{size // 1024}KB"
                    else:
                        size_str = f"{size // (1024 * 1024)}MB"
                    
                    # 尝试读取脚本备注（从同名的.txt文件）
                    note_file = file_path.replace('.sh', '.txt')
                    note = ""
                    if os.path.exists(note_file):
                        try:
                            with open(note_file, 'r', encoding='utf-8') as f:
                                note = f.read().strip()
                        except Exception as e:
                            print(f"读取备注文件失败 {note_file}: {str(e)}")
                    
                    scripts.append({
                        'name': filename,
                        'size': size_str,
                        'modified_time': modified_time,
                        'path': file_path,
                        'note': note
                    })
                    
                    print(f"找到脚本: {filename}")
                    
                except Exception as e:
                    print(f"处理脚本文件 {filename} 时出错: {str(e)}")
                    continue
        
        # 按文件名排序
        scripts.sort(key=lambda x: x['name'])
        
        print(f"\n总脚本数量: {len(scripts)}")
        print(f"所有脚本文件: {[script['name'] for script in scripts]}")
        
        # 测试不同的分页大小
        for page_size in [5, 10]:
            print(f"\n=== 测试分页大小: {page_size} ===")
            total_count = len(scripts)
            total_pages = (total_count + page_size - 1) // page_size
            
            print(f"总页数: {total_pages}")
            
            for page in range(1, total_pages + 1):
                start_index = (page - 1) * page_size
                end_index = min(start_index + page_size, total_count)
                
                # 获取当前页的数据
                current_page_scripts = scripts[start_index:end_index]
                actual_end_index = start_index + len(current_page_scripts)
                
                print(f"第 {page} 页: start_index={start_index}, end_index={end_index}, actual_end_index={actual_end_index}")
                print(f"脚本数量: {len(current_page_scripts)}")
                print(f"脚本列表: {[script['name'] for script in current_page_scripts]}")
                print("---")
    else:
        print(f"目录不存在: {scripts_dir}")

if __name__ == "__main__":
    test_pagination_logic() 