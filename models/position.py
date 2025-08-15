"""
职位模型模块
包含职位相关的数据模型定义
"""
from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from utils.snowflake import generate_position_id
from models.organization import Organization
from models.role import Role
from models.user import User

class Position(Base):
    """
    职位表模型,
    用于存储职位相关信息,
    包括职位ID、职位编码、职位名称、职位描述、是否启用、创建时间、更新时间
    需定义字段属性和注释,
    字段属性包括：id、code、name、description、is_active、created_at、updated_at
    注释包括：职位ID、职位编码、职位名称、职位描述、是否启用、创建时间、更新时间
    需定义构造方法,
    构造方法参数包括：id、code、name、description、is_active、created_at、updated_at
    需定义__repr__方法,
    __repr__方法返回值包括：id、name
    """
    __tablename__ = "positions"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_position_id, comment='职位ID，格式：P + 雪花算法ID')
    code = Column(String(100), nullable=False, unique=True, comment='职位编码')
    name = Column(String(100), nullable=False, unique=True, comment='职位名称')
    description = Column(Text, comment='职位描述')
    department_id = Column(String(25), ForeignKey('organizations.id'), comment='组织ID')
    department = Column(String(100), comment='组织名称')
    level = Column(String(100), comment='职位等级')
    is_active = Column(Boolean, default=True, comment='是否启用')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')  # 需要格式化时间yyyy-MM-dd HH:mm:ss
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')  # 需要格式化时间yyyy-MM-dd HH:mm:ss
    created_by = Column(String(25), ForeignKey('users.id'), comment='创建人ID')
    updated_by = Column(String(25), ForeignKey('users.id'), comment='更新人ID')
    
    users = relationship("User", foreign_keys="User.position_id", lazy="dynamic")
    organization = relationship("Organization", foreign_keys=[department_id])
    
    def __init__(self, code: str, name: str, description: str, department_id: str, is_active: bool = True):
        self.code = code
        self.name = name
        self.description = description
        self.department_id = department_id
        self.is_active = is_active
    
    
    def __repr__(self):
        return f"<Position(id={self.id}, code={self.code}, name={self.name}, department_id={self.department_id})>"