"""
模型模块初始化文件
提供向后兼容性和统一的导入接口
"""

# 导入数据库基础配置
from .database import Base, engine, SessionLocal, get_db

# 导入枚举类型
from .enums import (
    TaskStatus, TaskPriority, TaskType,
    ProjectStatus, ProjectPriority,
    UserRole, MemberRole,
    OrganizationType, OrganizationStatus,
    DefectStatus, DefectPriority, DefectType, DefectSeverity,
    CommentTargetType
)

# 导入关联表
from .associations import project_members, organization_members

# 导入模型类
from .user import User
from .organization import Organization
from .project import Project
from .task import Task, TaskAttachment, TaskComment
from .defect import Defect, DefectStatusHistory
from .position import Position
from .comment import Comment

# 为了向后兼容，将所有模型导出到models命名空间
__all__ = [
    # 数据库配置
    'Base', 'engine', 'SessionLocal', 'get_db',
    
    # 枚举类型
    'TaskStatus', 'TaskPriority', 'TaskType',
    'ProjectStatus', 'ProjectPriority',
    'UserRole', 'MemberRole',
    'OrganizationType', 'OrganizationStatus',
    'DefectStatus', 'DefectPriority', 'DefectType', 'DefectSeverity',
    'CommentTargetType',
    
    # 关联表
    'project_members', 'organization_members',
    
    # 模型类
    'User', 'Organization', 'Project',
    'Task', 'TaskAttachment', 'TaskComment',
    'Defect', 'DefectStatusHistory', 'Position', 'Comment'
]