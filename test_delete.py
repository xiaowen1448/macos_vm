import sqlite3
import sys
import os

def test_direct_db_delete():
    """直接测试数据库删除操作是否有效"""
    print("===== 开始直接数据库删除测试 =====")
    
    # 确保conn变量在所有情况下都有定义
    conn = None
    
    try:
        # 构建正确的数据库路径（根据get_db_connection函数的实现）
        db_dir = os.path.join(os.getcwd(), 'db')
        db_path = os.path.join(db_dir, 'apple_ids.db')
        
        # 检查数据库文件是否存在
        if not os.path.exists(db_path):
            print(f"数据库文件不存在: {db_path}")
            # 尝试找到数据库文件位置
            print("尝试查找数据库文件位置...")
            for root, dirs, files in os.walk(os.getcwd()):
                if 'apple_ids.db' in files:
                    db_path = os.path.join(root, 'apple_ids.db')
                    print(f"找到数据库文件: {db_path}")
                    break
            else:
                print("未找到apple_ids.db文件")
                return
        
        print(f"使用数据库路径: {db_path}")
        
        # 连接数据库
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        print("成功连接到数据库")
        
        # 获取要删除的进程ID（使用第一个记录）
        c.execute('SELECT id, name FROM processes LIMIT 1')
        process = c.fetchone()
        
        if not process:
            print("数据库中没有进程记录")
            return
        
        process_id, process_name = process
        print(f"将删除进程: ID={process_id}, 名称={process_name}")
        
        # 执行删除
        c.execute('DELETE FROM processes WHERE id = ?', (process_id,))
        affected_rows = c.rowcount
        conn.commit()
        
        print(f"删除操作执行完成，影响行数: {affected_rows}")
        
        # 验证删除结果
        c.execute('SELECT count(*) FROM processes WHERE id = ?', (process_id,))
        remaining_count = c.fetchone()[0]
        
        if remaining_count == 0:
            print(f"✅ 验证成功: 进程 {process_id} 已被成功删除")
        else:
            print(f"❌ 验证失败: 进程 {process_id} 仍然存在")
        
        # 显示当前所有记录
        print("\n删除后的进程列表:")
        c.execute('SELECT id, name FROM processes LIMIT 5')
        processes = c.fetchall()
        for p in processes:
            print(f"ID: {p[0]}, 名称: {p[1]}")
        
    except sqlite3.Error as e:
        print(f"SQLite错误: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            try:
                conn.close()
                print("数据库连接已关闭")
            except:
                pass
    
    print("===== 直接数据库删除测试结束 =====")

if __name__ == "__main__":
    test_direct_db_delete()