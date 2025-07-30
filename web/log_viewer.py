#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时日志查看工具
"""

import os
import time
import threading
from datetime import datetime

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

def monitor_log_directory():
    """监控日志目录"""
    log_dir = "."
    log_files = []
    
    print("扫描日志文件...")
    for file in os.listdir(log_dir):
        if file.endswith('.log'):
            log_files.append(file)
    
    if not log_files:
        print("未找到日志文件")
        return
    
    print("找到以下日志文件:")
    for i, file in enumerate(log_files, 1):
        size = os.path.getsize(file) if os.path.exists(file) else 0
        print(f"{i}. {file} ({size} 字节)")
    
    if len(log_files) == 1:
        choice = 1
    else:
        try:
            choice = int(input(f"选择要监控的文件 (1-{len(log_files)}): "))
            if choice < 1 or choice > len(log_files):
                print("无效选择")
                return
        except ValueError:
            print("无效输入")
            return
    
    selected_file = log_files[choice - 1]
    tail_log_file(selected_file)

if __name__ == "__main__":
    print("Flask应用日志监控工具")
    print("=" * 50)
    
    # 检查app_debug.log是否存在
    if os.path.exists("app_debug.log"):
        print("找到app_debug.log，开始监控...")
        tail_log_file("app_debug.log")
    else:
        print("app_debug.log不存在，扫描其他日志文件...")
        monitor_log_directory() 