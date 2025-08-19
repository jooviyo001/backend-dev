"""
关联表定义模块
包含多对多关系的关联表定义
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Table, Enum
from sqlalchemy.sql import func
from .database import Base
from .enums import MemberRole


# 项目成员关联表
project_members = Table(
    'project_members',
    Base.metadata,
    Column('project_id', String(25), ForeignKey('projects.id'), primary_key=True, comment='项目ID'),
    Column('user_id', String(25), ForeignKey('users.id'), primary_key=True, comment='用户ID'),
    Column('role', String(50), default='member', comment='成员角色')
)

# 组织成员关联表
organization_members = Table(
    'organization_members',
    Base.metadata,
    Column('department_id', String(25), ForeignKey('organizations.id'), primary_key=True, comment='组织ID'),
    Column('user_id', String(25), ForeignKey('users.id'), primary_key=True, comment='用户ID'),
    Column('position', String(100), comment='职位'),
    Column('role', Enum(MemberRole), default=MemberRole.MEMBER, comment='成员角色'),
    Column('joined_at', DateTime, default=func.now(), comment='加入时间')
)