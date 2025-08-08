"""
组织模型模块
包含组织相关的数据模型定义
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from .enums import OrganizationType, OrganizationStatus
from .associations import organization_members
from utils.snowflake import generate_organization_id


class Organization(Base):
    """组织表模型"""
    __tablename__ = "organizations"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_organization_id, comment='组织ID，格式：O + 雪花算法ID')
    name = Column(String(100), nullable=False, comment='组织名称')
    code = Column(String(20), unique=True, nullable=False, index=True, comment='组织编码，唯一标识')
    type = Column(Enum(OrganizationType), nullable=False, comment='组织类型')
    status = Column(Enum(OrganizationStatus), default=OrganizationStatus.ACTIVE, comment='组织状态')
    description = Column(Text, comment='组织描述')
    parent_id = Column(String(25), ForeignKey("organizations.id"), comment='父组织ID')
    level = Column(Integer, default=1, comment='组织层级')
    path = Column(String(500), comment='组织路径，如 "/1/2/3"')
    manager_id = Column(String(25), ForeignKey("users.id"), comment='组织管理员ID')
    sort = Column(Integer, default=0, comment='排序字段')
    address = Column(String(255), comment='组织地址')
    phone = Column(String(20), comment='联系电话')
    email = Column(String(100), comment='联系邮箱')
    website = Column(String(255), comment='官方网站')
    logo = Column(String(255), comment='组织Logo URL')
    is_active = Column(Boolean, default=True, comment='是否激活状态，保留兼容性')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关系
    parent = relationship("Organization", remote_side=[id], back_populates="children")
    children = relationship("Organization", back_populates="parent")
    manager = relationship("User", foreign_keys=[manager_id])
    projects = relationship("Project", back_populates="organization")
    members = relationship("User", secondary=organization_members, back_populates="organizations")