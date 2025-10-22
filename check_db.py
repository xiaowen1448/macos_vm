# -*- coding: utf-8 -*-
import sqlite3
from pathlib import Path
import json

# 获取数据库连接
def get_db_connection():
    db_dir = Path(__file__).parent / 'db'
    db_path = db_dir / 'apple_ids.db'
    
    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}")
        return None
    
    conn = sqlite3.connect(db_path)
    return conn

def check_processes_table():
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        c = conn.cursor()
        
        # 检查表结构
        print("\n===== 检查 processes 表结构 =====")
        c.execute("PRAGMA table_info(processes)")
        columns = c.fetchall()
        print(f"表字段数: {len(columns)}")
        for column in columns:
            print(f"字段: {column[1]}, 类型: {column[2]}")
        
        # 查询所有进程记录
        print("\n===== 所有进程记录 =====")
        c.execute("SELECT COUNT(*) FROM processes")
        count = c.fetchone()[0]
        print(f"进程总数: {count}")
        
        if count > 0:
            c.execute("SELECT id, name, status, create_time FROM processes ORDER BY create_time DESC")
            processes = c.fetchall()
            print("进程列表:")
            for process in processes:
                print(f"ID: {process[0]}, 名称: {process[1]}, 状态: {process[2]}, 创建时间: {process[3]}")
        
    except Exception as e:
        print(f"查询数据库时出错: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("开始检查数据库...")
    check_processes_table()
    print("\n检查完成!")