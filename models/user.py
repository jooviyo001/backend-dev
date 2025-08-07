"""
用户模型模块
包含用户相关的数据模型定义
"""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from .enums import UserRole
from .associations import project_members, organization_members
from utils.snowflake import generate_user_id


class User(Base):
    """用户表模型"""
    __tablename__ = "users"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_user_id, comment='用户ID，格式：U + 雪花算法ID')
    username = Column(String(50), unique=True, index=True, nullable=False, comment='用户名，唯一标识')
    email = Column(String(100), unique=True, index=True, nullable=False, comment='邮箱地址，唯一标识')
    password_hash = Column(String(255), nullable=False, comment='密码哈希值')
    name = Column(String(100), comment='用户真实姓名')
    avatar = Column(String(255), comment='头像URL地址')
    phone = Column(String(20), comment='手机号码')
    position = Column(String(100), comment='用户岗位/职位')
    department = Column(String(100), comment='用户所属部门')
    organization_id = Column(String(25), ForeignKey("organizations.id"), comment='用户所属组织ID')
    role = Column(Enum(UserRole), default=UserRole.MEMBER, comment='用户角色')
    is_active = Column(Boolean, default=True, comment='是否激活状态')
    is_verified = Column(Boolean, default=False, comment='是否已验证邮箱')
    last_login = Column(DateTime, comment='最后登录时间')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关系
    organization = relationship("Organization", foreign_keys=[organization_id])
    created_projects = relationship("Project", back_populates="creator", foreign_keys="Project.creator_id")
    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")
    reported_tasks = relationship("Task", back_populates="reporter", foreign_keys="Task.reporter_id")
    projects = relationship("Project", secondary=project_members, back_populates="members")
    organizations = relationship("Organization", secondary=organization_members, back_populates="members")