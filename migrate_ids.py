"""
数据库ID格式迁移脚本
将现有的纯数字ID更新为带前缀的格式：
- 用户: U + ID
- 组织: O + ID  
- 项目: P + ID
- 任务: T + ID
- 任务附件: TA + ID
- 任务评论: TC + ID
"""

import sqlite3
from pathlib import Path

def migrate_database():
    """执行数据库ID格式迁移"""
    db_path = Path("backend.db")
    
    if not db_path.exists():
        print("数据库文件不存在，跳过迁移")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        print("开始数据库ID格式迁移...")
        
        # 1. 备份原始数据
        print("1. 创建备份表...")
        backup_tables = [
            "CREATE TABLE IF NOT EXISTS users_backup AS SELECT * FROM users",
            "CREATE TABLE IF NOT EXISTS organizations_backup AS SELECT * FROM organizations", 
            "CREATE TABLE IF NOT EXISTS projects_backup AS SELECT * FROM projects",
            "CREATE TABLE IF NOT EXISTS tasks_backup AS SELECT * FROM tasks",
            "CREATE TABLE IF NOT EXISTS task_attachments_backup AS SELECT * FROM task_attachments",
            "CREATE TABLE IF NOT EXISTS task_comments_backup AS SELECT * FROM task_comments",
            "CREATE TABLE IF NOT EXISTS project_members_backup AS SELECT * FROM project_members",
            "CREATE TABLE IF NOT EXISTS organization_members_backup AS SELECT * FROM organization_members"
        ]
        
        for sql in backup_tables:
            cursor.execute(sql)
        
        # 2. 更新用户表ID
        print("2. 更新用户表ID格式...")
        cursor.execute("SELECT id FROM users WHERE id NOT LIKE 'U%'")
        user_ids = cursor.fetchall()
        
        for (old_id,) in user_ids:
            new_id = f"U{old_id}"
            
            # 更新用户表
            cursor.execute("UPDATE users SET id = ? WHERE id = ?", (new_id, old_id))
            
            # 更新相关外键
            cursor.execute("UPDATE organizations SET manager_id = ? WHERE manager_id = ?", (new_id, old_id))
            cursor.execute("UPDATE projects SET creator_id = ? WHERE creator_id = ?", (new_id, old_id))
            cursor.execute("UPDATE projects SET manager_id = ? WHERE manager_id = ?", (new_id, old_id))
            cursor.execute("UPDATE tasks SET assignee_id = ? WHERE assignee_id = ?", (new_id, old_id))
            cursor.execute("UPDATE tasks SET reporter_id = ? WHERE reporter_id = ?", (new_id, old_id))
            cursor.execute("UPDATE task_attachments SET uploaded_by = ? WHERE uploaded_by = ?", (new_id, old_id))
            cursor.execute("UPDATE task_comments SET user_id = ? WHERE user_id = ?", (new_id, old_id))
            cursor.execute("UPDATE project_members SET user_id = ? WHERE user_id = ?", (new_id, old_id))
            cursor.execute("UPDATE organization_members SET user_id = ? WHERE user_id = ?", (new_id, old_id))
        
        # 3. 更新组织表ID
        print("3. 更新组织表ID格式...")
        cursor.execute("SELECT id FROM organizations WHERE id NOT LIKE 'O%'")
        org_ids = cursor.fetchall()
        
        for (old_id,) in org_ids:
            new_id = f"O{old_id}"
            
            # 更新组织表
            cursor.execute("UPDATE organizations SET id = ? WHERE id = ?", (new_id, old_id))
            
            # 更新相关外键
            cursor.execute("UPDATE organizations SET parent_id = ? WHERE parent_id = ?", (new_id, old_id))
            cursor.execute("UPDATE users SET organization_id = ? WHERE organization_id = ?", (new_id, old_id))
            cursor.execute("UPDATE projects SET organization_id = ? WHERE organization_id = ?", (new_id, old_id))
            cursor.execute("UPDATE organization_members SET organization_id = ? WHERE organization_id = ?", (new_id, old_id))
        
        # 4. 更新项目表ID
        print("4. 更新项目表ID格式...")
        cursor.execute("SELECT id FROM projects WHERE id NOT LIKE 'P%'")
        project_ids = cursor.fetchall()
        
        for (old_id,) in project_ids:
            new_id = f"P{old_id}"
            
            # 更新项目表
            cursor.execute("UPDATE projects SET id = ? WHERE id = ?", (new_id, old_id))
            
            # 更新相关外键
            cursor.execute("UPDATE tasks SET project_id = ? WHERE project_id = ?", (new_id, old_id))
            cursor.execute("UPDATE project_members SET project_id = ? WHERE project_id = ?", (new_id, old_id))
        
        # 5. 更新任务表ID
        print("5. 更新任务表ID格式...")
        cursor.execute("SELECT id FROM tasks WHERE id NOT LIKE 'T%'")
        task_ids = cursor.fetchall()
        
        for (old_id,) in task_ids:
            new_id = f"T{old_id}"
            
            # 更新任务表
            cursor.execute("UPDATE tasks SET id = ? WHERE id = ?", (new_id, old_id))
            
            # 更新相关外键
            cursor.execute("UPDATE tasks SET parent_task_id = ? WHERE parent_task_id = ?", (new_id, old_id))
            cursor.execute("UPDATE task_attachments SET task_id = ? WHERE task_id = ?", (new_id, old_id))
            cursor.execute("UPDATE task_comments SET task_id = ? WHERE task_id = ?", (new_id, old_id))
        
        # 6. 更新任务附件表ID
        print("6. 更新任务附件表ID格式...")
        cursor.execute("SELECT id FROM task_attachments WHERE id NOT LIKE 'TA%'")
        attachment_ids = cursor.fetchall()
        
        for (old_id,) in attachment_ids:
            new_id = f"TA{old_id}"
            cursor.execute("UPDATE task_attachments SET id = ? WHERE id = ?", (new_id, old_id))
        
        # 7. 更新任务评论表ID
        print("7. 更新任务评论表ID格式...")
        cursor.execute("SELECT id FROM task_comments WHERE id NOT LIKE 'TC%'")
        comment_ids = cursor.fetchall()
        
        for (old_id,) in comment_ids:
            new_id = f"TC{old_id}"
            cursor.execute("UPDATE task_comments SET id = ? WHERE id = ?", (new_id, old_id))
        
        # 提交事务
        conn.commit()
        print("✅ 数据库ID格式迁移完成！")
        
        # 显示迁移统计
        print("\n迁移统计:")
        print(f"- 用户ID: {len(user_ids)} 条记录")
        print(f"- 组织ID: {len(org_ids)} 条记录") 
        print(f"- 项目ID: {len(project_ids)} 条记录")
        print(f"- 任务ID: {len(task_ids)} 条记录")
        print(f"- 任务附件ID: {len(attachment_ids)} 条记录")
        print(f"- 任务评论ID: {len(comment_ids)} 条记录")
        
    except Exception as e:
        print(f"❌ 迁移过程中出现错误: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()