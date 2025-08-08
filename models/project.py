"""
项目模型模块
包含项目相关的数据模型定义
"""
from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey, Enum, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from .enums import ProjectStatus, ProjectPriority
from .associations import project_members
from utils.snowflake import generate_project_id


class Project(Base):
    """项目表模型"""
    __tablename__ = "projects"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_project_id, comment='项目ID，格式：P + 雪花算法ID')
    name = Column(String(100), nullable=False, comment='项目名称')
    description = Column(Text, comment='项目描述')
    status = Column(Enum(ProjectStatus), default=ProjectStatus.PLANNING, comment='项目状态')
    priority = Column(Enum(ProjectPriority), default=ProjectPriority.MEDIUM, comment='项目优先级')
    start_date = Column(DateTime, comment='项目开始日期')
    end_date = Column(DateTime, comment='项目结束日期')
    creator_id = Column(String(25), ForeignKey("users.id"), comment='项目创建者ID')
    manager_id = Column(String(25), ForeignKey("users.id"), comment='项目管理者ID')
    organization_id = Column(String(25), ForeignKey("organizations.id"), comment='所属组织ID')
    budget = Column(Numeric(15, 2), comment='项目预算，数值类型，≥0')
    tags = Column(String(500), comment='项目标签，JSON字符串存储标签数组')
    is_archived = Column(Boolean, default=False, comment='是否已归档')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关系
    creator = relationship("User", back_populates="created_projects", foreign_keys=[creator_id])
    manager = relationship("User", foreign_keys=[manager_id])
    organization = relationship("Organization", back_populates="projects")
    tasks = relationship("Task", back_populates="project")
    members = relationship("User", secondary=project_members, back_populates="projects")