#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志管理工具
用于清理旧的日志文件和管理日志目录
"""

import os
import datetime
import glob
from config import logs_dir, LOG_FILE_RETENTION_DAYS

def get_log_directory():
    """获取日志目录路径"""
    return os.path.join(os.path.dirname(__file__), logs_dir)

def list_log_files():
    """列出所有日志文件"""
    log_dir = get_log_directory()
    if not os.path.exists(log_dir):
        print(f"日志目录不存在: {log_dir}")
        return []
    
    log_files = []
    for file in os.listdir(log_dir):
        if file.endswith('.log'):
            file_path = os.path.join(log_dir, file)
            try:
                size = os.path.getsize(file_path)
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                log_files.append({
                    'name': file,
                    'path': file_path,
                    'size': size,
                    'mtime': mtime
                })
            except Exception as e:
                print(f"获取文件信息失败: {file} - {e}")
    
    return sorted(log_files, key=lambda x: x['mtime'], reverse=True)

def clean_old_logs():
    """清理旧的日志文件"""
    log_dir = get_log_directory()
    if not os.path.exists(log_dir):
        print(f"日志目录不存在: {log_dir}")
        return
    
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=LOG_FILE_RETENTION_DAYS)
    deleted_count = 0
    deleted_size = 0
    
    print(f"清理 {LOG_FILE_RETENTION_DAYS} 天前的日志文件...")
    
    for file in os.listdir(log_dir):
        if file.endswith('.log'):
            file_path = os.path.join(log_dir, file)
            try:
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                if mtime < cutoff_date:
                    size = os.path.getsize(file_path)
                    os.remove(file_path)
                    deleted_count += 1
                    deleted_size += size
                    print(f"已删除: {file} (大小: {size/1024/1024:.2f} MB)")
            except Exception as e:
                print(f"删除文件失败: {file} - {e}")
    
    print(f"清理完成！删除了 {deleted_count} 个文件，释放了 {deleted_size/1024/1024:.2f} MB 空间")

def show_log_stats():
    """显示日志统计信息"""
    log_files = list_log_files()
    
    if not log_files:
        print("没有找到日志文件")
        return
    
    total_size = sum(f['size'] for f in log_files)
    total_count = len(log_files)
    
    print("日志文件统计:")
    print(f"总文件数: {total_count}")
    print(f"总大小: {total_size/1024/1024:.2f} MB")
    print(f"保留天数: {LOG_FILE_RETENTION_DAYS} 天")
    print()
    
    print("最近的日志文件:")
    for i, file_info in enumerate(log_files[:10], 1):
        size_mb = file_info['size'] / (1024 * 1024)
        mtime_str = file_info['mtime'].strftime('%Y-%m-%d %H:%M:%S')
        print(f"{i}. {file_info['name']} ({size_mb:.2f} MB, {mtime_str})")

def main():
    """主函数"""
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'clean':
            clean_old_logs()
        elif command == 'list':
            log_files = list_log_files()
            for file_info in log_files:
                size_mb = file_info['size'] / (1024 * 1024)
                mtime_str = file_info['mtime'].strftime('%Y-%m-%d %H:%M:%S')
                print(f"{file_info['name']} ({size_mb:.2f} MB, {mtime_str})")
        elif command == 'stats':
            show_log_stats()
        else:
            print("未知命令。可用命令: clean, list, stats")
    else:
        print("日志管理工具")
        print("=" * 30)
        print("用法: python log_manager.py [命令]")
        print("命令:")
        print("  clean  - 清理旧的日志文件")
        print("  list   - 列出所有日志文件")
        print("  stats  - 显示日志统计信息")
        print()
        show_log_stats()

if __name__ == "__main__":
    main() 