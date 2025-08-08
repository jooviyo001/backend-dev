"""
缺陷模型模块
包含缺陷相关的数据模型定义
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from .enums import DefectStatus, DefectPriority, DefectType, DefectSeverity
from utils.snowflake import generate_defect_id


class Defect(Base):
    """缺陷表模型"""
    __tablename__ = "defects"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_defect_id, comment='缺陷ID，格式：D + 雪花算法ID')
    title = Column(String(200), nullable=False, comment='缺陷标题')
    description = Column(Text, comment='缺陷描述')
    status = Column(Enum(DefectStatus), default=DefectStatus.NEW, comment='缺陷状态')
    priority = Column(Enum(DefectPriority), default=DefectPriority.MEDIUM, comment='缺陷优先级')
    type = Column(Enum(DefectType), default=DefectType.BUG, comment='缺陷类型')
    project_id = Column(String(25), ForeignKey("projects.id"), comment='缺陷所属项目ID')
    project_name = Column(String(100), comment='缺陷所属项目名称')
    assignee_id = Column(String(25), ForeignKey("users.id"), comment='缺陷负责人ID')
    assignee_name = Column(String(100), comment='缺陷负责人姓名')
    reporter_id = Column(String(25), ForeignKey("users.id"), comment='缺陷报告人ID')
    reporter_name = Column(String(100), comment='缺陷报告人姓名')
    verified_by_id = Column(String(25), ForeignKey("users.id"), nullable=True, comment='缺陷验证人ID')
    verified_by_name = Column(String(100), nullable=True, comment='缺陷验证人姓名')
    severity = Column(Enum(DefectSeverity), default=DefectSeverity.MODERATE, comment='缺陷严重程度')
    version = Column(String(100), comment='缺陷所属版本')
    environment = Column(String(100), comment='缺陷所属环境')
    steps_to_reproduce = Column(Text, comment='复现步骤')
    expected_result = Column(Text, comment='预期结果')
    actual_result = Column(Text, comment='实际结果')
    resolution = Column(Text, comment='解决方法')
    tags = Column(String(500), comment='缺陷标签')  # JSON字符串存储标签
    parent_id = Column(String(25), ForeignKey("defects.id"), nullable=True, comment='父缺陷ID')
    source = Column(String(100), nullable=True, comment='缺陷来源')
    created_by = Column(String(25), ForeignKey("users.id"), comment='创建人ID')
    updated_by = Column(String(25), ForeignKey("users.id"), nullable=True, comment='更新人ID')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    due_date = Column(DateTime, nullable=True, comment='截止时间')
    
    # 关系
    project = relationship("Project")
    assignee = relationship("User", foreign_keys=[assignee_id])
    reporter = relationship("User", foreign_keys=[reporter_id])
    parent_defect = relationship("Defect", remote_side=[id], back_populates="sub_defects")
    sub_defects = relationship("Defect", back_populates="parent_defect")