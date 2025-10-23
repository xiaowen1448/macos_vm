import sqlite3
import json
import os

# 连接到数据库
db_path = os.path.join(os.getcwd(), 'db', 'apple_ids.db')
print(f"数据库路径: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 获取所有表名
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"数据库中的表: {tables}")
    
    # 检查是否有进程相关的表
    process_tables = [table[0] for table in tables if 'process' in table[0].lower()]
    print(f"进程相关表: {process_tables}")
    
    # 查询每个进程表的内容
    for table in process_tables:
        print(f"\n查询表: {table}")
        cursor.execute(f"SELECT * FROM {table};")
        rows = cursor.fetchall()
        
        # 获取列名
        columns = [desc[0] for desc in cursor.description]
        print(f"列名: {columns}")
        
        # 打印所有记录，特别关注状态为"启动中"或类似的记录
        print("\n记录:")
        for row in rows:
            row_dict = dict(zip(columns, row))
            # 特别标记状态相关的记录
            status = row_dict.get('status', '').lower()
            if '启动中' in status or 'starting' in status or 'waiting' in status:
                print("\n===== 虚拟机启动中的进程 =====")
                for key, value in row_dict.items():
                    print(f"  {key}: {value}")
            else:
                # 只打印基本信息，避免输出过多
                basic_info = {k: v for k, v in row_dict.items() if k in ['id', 'status', 'vm_ip', 'create_time']}
                print(f"  {basic_info}")
    
    # 额外检查是否有vm相关的表
    vm_tables = [table[0] for table in tables if 'vm' in table[0].lower()]
    if vm_tables:
        print(f"\n虚拟机相关表: {vm_tables}")
        for table in vm_tables:
            print(f"\n查询表: {table}")
            cursor.execute(f"SELECT * FROM {table} LIMIT 5;")  # 只查询前5条记录
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            print(f"列名: {columns}")
            for row in rows:
                row_dict = dict(zip(columns, row))
                print(f"  {row_dict}")
    
    conn.close()
    
except Exception as e:
    print(f"查询数据库时出错: {e}")
    import traceback
    traceback.print_exc()