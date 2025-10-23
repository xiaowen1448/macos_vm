import sqlite3
import os

# 连接到数据库
db_path = os.path.join('db', 'apple_ids.db')

# 进程ID
process_id = '91e3b7e1-70fb-4119-88d2-390314b0ab65'

try:
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查进程是否存在
    cursor.execute("SELECT status FROM processes WHERE id = ?", (process_id,))
    result = cursor.fetchone()
    
    if result:
        current_status = result[0]
        print(f"当前进程状态: {current_status}")
        
        # 更新进程状态
        cursor.execute("UPDATE processes SET status = '运行中' WHERE id = ?", (process_id,))
        conn.commit()
        
        # 验证更新
        cursor.execute("SELECT status FROM processes WHERE id = ?", (process_id,))
        new_status = cursor.fetchone()[0]
        print(f"进程状态已更新为: {new_status}")
        print(f"已成功将进程 {process_id} 状态从 '{current_status}' 更新为 '{new_status}'")
    else:
        print(f"未找到进程ID: {process_id}")
        
except sqlite3.Error as e:
    print(f"数据库操作错误: {e}")
finally:
    if conn:
        conn.close()