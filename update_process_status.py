import sqlite3
import os

# 连接到数据库
db_path = os.path.join(os.getcwd(), 'db', 'apple_ids.db')
print(f"数据库路径: {db_path}")

# 要更新的进程ID
process_id = '91e3b7e1-70fb-4119-88d2-390314b0ab65'

# 新状态
new_status = '运行中'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 首先检查进程是否存在
    cursor.execute("SELECT * FROM processes WHERE id = ?", (process_id,))
    process = cursor.fetchone()
    
    if process:
        print(f"找到进程: {process}")
        
        # 更新进程状态
        cursor.execute("UPDATE processes SET status = ? WHERE id = ?", (new_status, process_id))
        conn.commit()
        
        # 验证更新是否成功
        cursor.execute("SELECT status FROM processes WHERE id = ?", (process_id,))
        updated_status = cursor.fetchone()[0]
        print(f"进程状态更新成功！")
        print(f"原状态: 启动中")
        print(f"新状态: {updated_status}")
    else:
        print(f"未找到进程: {process_id}")
    
    conn.close()
    
except Exception as e:
    print(f"更新数据库时出错: {e}")
    import traceback
    traceback.print_exc()