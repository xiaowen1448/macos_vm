#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时日志查看工具 - 支持带日期的日志文件
"""

import os
import time
import datetime
from datetime import datetime

def get_log_files(log_dir):
    """获取日志目录下的所有日志文件"""
    log_files = []
    if os.path.exists(log_dir):
        for file in os.listdir(log_dir):
            if file.endswith('.log'):
                file_path = os.path.join(log_dir, file)
                # 获取文件大小和修改时间
                try:
                    size = os.path.getsize(file_path)
                    mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    log_files.append({
                        'name': file,
                        'path': file_path,
                        'size': size,
                        'mtime': mtime
                    })
                except Exception as e:
                    print(f"获取文件信息失败: {file} - {e}")
    
    # 按修改时间排序，最新的在前面
    log_files.sort(key=lambda x: x['mtime'], reverse=True)
    return log_files

def tail_log_file(log_file_path, max_lines=100):
    """实时查看日志文件"""
    print(f"开始监控日志文件: {log_file_path}")
    print("=" * 80)
    
    # 如果文件不存在，等待创建
    while not os.path.exists(log_file_path):
        print(f"等待日志文件创建: {log_file_path}")
        time.sleep(1)
    
    # 获取文件大小
    file_size = os.path.getsize(log_file_path)
    print(f"日志文件大小: {file_size} 字节")
    
    # 读取最后几行
    with open(log_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
        
        print("最近日志:")
        for line in lines:
            print(line.rstrip())
    
    print("\n" + "=" * 80)
    print("开始实时监控 (按 Ctrl+C 停止)...")
    
    # 实时监控
    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            # 移动到文件末尾
            f.seek(0, 2)
            
            while True:
                line = f.readline()
                if line:
                    print(line.rstrip())
                else:
                    time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n停止监控")

def select_log_file(log_dir):
    """选择要监控的日志文件"""
    log_files = get_log_files(log_dir)
    
    if not log_files:
        print("未找到日志文件")
        return None
    
    print("找到以下日志文件:")
    for i, file_info in enumerate(log_files, 1):
        size_mb = file_info['size'] / (1024 * 1024)
        mtime_str = file_info['mtime'].strftime('%Y-%m-%d %H:%M:%S')
        print(f"{i}. {file_info['name']} ({size_mb:.2f} MB, 修改时间: {mtime_str})")
    
    if len(log_files) == 1:
        return log_files[0]['path']
    else:
        try:
            choice = int(input(f"选择要监控的文件 (1-{len(log_files)}): "))
            if choice < 1 or choice > len(log_files):
                print("无效选择")
                return None
            return log_files[choice - 1]['path']
        except ValueError:
            print("无效输入")
            return None

def main():
    """主函数"""
    print("Flask应用日志监控工具")
    print("=" * 50)
    
    # 检查log目录下的日志文件
    from config import logs_dir
    log_dir = os.path.join(os.path.dirname(__file__), logs_dir)
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # 尝试找到今天的app_debug日志文件
    app_debug_log = os.path.join(log_dir, f"app_debug_{current_date}.log")
    
    if os.path.exists(app_debug_log):
        print(f"找到今天的日志文件: {os.path.basename(app_debug_log)}")
        tail_log_file(app_debug_log)
    else:
        print("未找到今天的日志文件，请选择要监控的文件:")
        selected_file = select_log_file(log_dir)
        if selected_file:
            tail_log_file(selected_file)
        else:
            print("未选择文件，退出")

if __name__ == "__main__":
    main() 