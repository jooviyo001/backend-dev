"""评论模型模块
包含评论相关的数据模型定义
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from .enums import CommentTargetType
from utils.snowflake import generate_comment_id


class Comment(Base):
    """评论表模型"""
    __tablename__ = "comments"
    
    id = Column(String(25), primary_key=True, index=True, default=generate_comment_id, comment='评论ID，格式：C + 雪花算法ID')
    content = Column(Text, nullable=False, comment='评论内容')
    target_type = Column(Enum(CommentTargetType), nullable=False, comment='评论目标类型')
    target_id = Column(String(25), nullable=False, comment='评论目标ID')
    author_id = Column(String(25), ForeignKey("users.id"), nullable=False, comment='评论作者ID')
    parent_id = Column(String(25), ForeignKey('comments.id'), nullable=True, comment='父评论ID，用于回复功能')
    created_at = Column(DateTime, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 关系
    author = relationship("User", back_populates="comments")
    parent = relationship("Comment", remote_side=[id], back_populates="replies")
    replies = relationship("Comment", back_populates="parent", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Comment(id={self.id}, target_type={self.target_type}, target_id={self.target_id})>"