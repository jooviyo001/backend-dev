"""文档管理模型模块
包含文档和文件夹相关的数据模型定义
"""
from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey, Enum, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from .enums import DocumentType
from utils.snowflake import generate_document_id
from models.base import BaseModelMixin


class Document(Base, BaseModelMixin):
    """文档/文件夹表模型"""
    __tablename__ = "documents"
    
    id = Column(String(27), primary_key=True, index=True, default=generate_document_id, comment='文档ID，格式：DOC + 雪花算法ID')
    name = Column(String(255), nullable=False, comment='文档/文件夹名称')
    type = Column(Enum(DocumentType), nullable=False, comment='类型：文件夹或文档')
    parent_id = Column(String(27), ForeignKey("documents.id"), nullable=True, comment='父级文件夹ID，根目录为NULL')
    file_type = Column(String(50), nullable=True, comment='文件类型（仅文档类型）')
    file_size = Column(BigInteger, nullable=True, comment='文件大小（字节，仅文档类型）')
    file_path = Column(String(500), nullable=True, comment='文件存储路径（MinIO路径）')
    mime_type = Column(String(100), nullable=True, comment='MIME类型')
    bucket_name = Column(String(100), nullable=True, comment='MinIO存储桶名称')
    object_key = Column(String(500), nullable=True, comment='MinIO对象键')
    checksum = Column(String(64), nullable=True, comment='文件校验和（MD5）')
    description = Column(Text, nullable=True, comment='文档描述')
    created_by = Column(String(25), ForeignKey("users.id"), nullable=False, comment='创建人ID')
    updated_by = Column(String(25), ForeignKey("users.id"), nullable=True, comment='更新人ID')
    
    # 关系
    parent = relationship("Document", remote_side=[id], back_populates="children")
    children = relationship("Document", back_populates="parent", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    
    def __repr__(self):
        return f"<Document(id={self.id}, name={self.name}, type={self.type})>"
    
    @property
    def is_folder(self):
        """是否为文件夹"""
        return self.type == DocumentType.FOLDER
    
    @property
    def is_document(self):
        """是否为文档"""
        return self.type == DocumentType.DOCUMENT
    
    def get_full_path(self):
        """获取完整路径"""
        if self.parent is None:
            return self.name
        return f"{self.parent.get_full_path()}/{self.name}"