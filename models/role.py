# 定义角色模型
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from utils.snowflake import generate_role_id
from models.base import BaseModelMixin

class Role(Base, BaseModelMixin):
    """
    角色表模型,
    用于存储角色相关信息,
    包括角色ID、角色编码、角色名称、角色描述、是否启用、创建时间、更新时间
    需定义字段属性和注释,
    字段属性包括：id、code、name、description、is_active、created_at、updated_at
    注释包括：角色ID、角色编码、角色名称、角色描述、是否启用、创建时间、更新时间
    需定义构造方法,
    构造方法参数包括：id、code、name、description、is_active、created_at、updated_at
    需定义__repr__方法,
    __repr__方法返回值包括：id、name、code、description、is_active、created_at、updated_at
    需定义__str__方法,
    __str__方法返回值包括：id、name、code、description、is_active、created_at、updated_at
    需定义__eq__方法,
    __eq__方法参数包括：self、other
    __eq__方法返回值包括：self.id == other.id
    需定义__hash__方法,
    __hash__方法返回值包括：hash(self.id)

    """
    __tablename__ = "roles"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_role_id, comment='角色ID，格式：R + 雪花算法ID')
    code = Column(String(100), nullable=False, unique=True, comment='角色编码')
    name = Column(String(100), nullable=False, unique=True, comment='角色名称')
    description = Column(Text, comment='角色描述')
    is_active = Column(Boolean, default=True, comment='是否启用')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    users = relationship("User", back_populates="user_role", lazy="dynamic", overlaps="user_role")
    
    # 权限关联关系（需要在permission.py导入后才能使用）
    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles", lazy="dynamic")

    def __init__(self, code: str, name: str, description: str, is_active: bool = True):
        self.code = code
        self.name = name
        self.description = description
        self.is_active = is_active
        self.created_at = func.now()
        self.updated_at = func.now()
    def __repr__(self):
        return f"<Role(id={self.id}, code={self.code}, name={self.name}, description={self.description}, is_active={self.is_active}, created_at={self.created_at}, updated_at={self.updated_at})>"
    def __str__(self):
        return f"<Role(id={self.id}, code={self.code}, name={self.name}, description={self.description}, is_active={self.is_active}, created_at={self.created_at}, updated_at={self.updated_at})>"
    def __eq__(self, other):
        return self.id == other.id
    def __hash__(self):
        return hash(self.id)




