"""数据库索引优化模块

为常用查询字段添加复合索引，提升查询性能
"""

from sqlalchemy import Index
from models.task import Task
from models.user import User
from models.project import Project
from models.defect import Defect
from models.organization import Organization


def create_database_indexes():
    """创建数据库索引"""
    indexes = [
        # 任务表索引
        Index('idx_task_status_priority', Task.status, Task.priority),
        Index('idx_task_project_assignee', Task.project_id, Task.assignee_id),
        Index('idx_task_created_at', Task.created_at.desc()),
        Index('idx_task_due_date', Task.due_date),
        Index('idx_task_soft_delete', Task.is_deleted, Task.deleted_at),
        
        # 用户表索引
        Index('idx_user_email', User.email),
        Index('idx_user_username', User.username),
        Index('idx_user_role_status', User.role, User.is_active),
        Index('idx_user_soft_delete', User.is_deleted, User.deleted_at),
        
        # 项目表索引
        Index('idx_project_status', Project.status),
        Index('idx_project_organization', Project.department_id),
        Index('idx_project_created_at', Project.created_at.desc()),
        Index('idx_project_soft_delete', Project.is_deleted, Project.deleted_at),
        
        # 缺陷表索引 - 基础索引
        Index('idx_defect_status_priority', Defect.status, Defect.priority),
        Index('idx_defect_project_assignee', Defect.project_id, Defect.assignee_id),
        Index('idx_defect_severity', Defect.severity),
        Index('idx_defect_created_at', Defect.created_at.desc()),
        Index('idx_defect_soft_delete', Defect.is_deleted, Defect.deleted_at),
        
        # 缺陷表复合索引 - 提升查询性能
        Index('idx_defect_project_status_priority', Defect.project_id, Defect.status, Defect.priority),
        Index('idx_defect_assignee_status', Defect.assignee_id, Defect.status),
        Index('idx_defect_severity_type', Defect.severity, Defect.defect_type),
        Index('idx_defect_reporter_created', Defect.reporter_id, Defect.created_at.desc()),
        Index('idx_defect_status_updated', Defect.status, Defect.updated_at.desc()),
        Index('idx_defect_priority_due_date', Defect.priority, Defect.due_date),
        Index('idx_defect_project_severity', Defect.project_id, Defect.severity),
        Index('idx_defect_assignee_priority', Defect.assignee_id, Defect.priority),
        
        # 缺陷统计查询优化索引
        Index('idx_defect_stats_combo', Defect.is_deleted, Defect.status, Defect.priority, Defect.severity),
        
        # 组织表索引
        Index('idx_organization_type_status', Organization.type, Organization.status),
        Index('idx_organization_created_at', Organization.created_at.desc()),
        Index('idx_organization_soft_delete', Organization.is_deleted, Organization.deleted_at),
    ]
    
    return indexes


def apply_indexes_to_metadata(metadata):
    """将索引应用到元数据"""
    indexes = create_database_indexes()
    
    for index in indexes:
        # 将索引添加到对应表的元数据中
        table = index.table
        if table is not None:
            table.append_constraint(index)
    
    print(f"✅ 已创建 {len(indexes)} 个数据库索引")
    return indexes