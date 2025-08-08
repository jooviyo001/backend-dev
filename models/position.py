"""
职位模型模块
包含职位相关的数据模型定义
"""
from sqlalchemy import Column, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from .database import Base
from utils.snowflake import generate_position_id


class Position(Base):
    """职位表模型"""
    __tablename__ = "positions"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_position_id, comment='职位ID，格式：P + 雪花算法ID')
    name = Column(String(100), nullable=False, unique=True, comment='职位名称')
    description = Column(Text, comment='职位描述')
    is_active = Column(Boolean, default=True, comment='是否启用')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    def __repr__(self):
        return f"<Position(id={self.id}, name={self.name})>"