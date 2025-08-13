"""评论相关的Pydantic模型
用于API接口的数据验证和序列化
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from models.enums import CommentTargetType


class CommentBase(BaseModel):
    """评论基础模型"""
    content: str = Field(..., min_length=1, max_length=5000, description="评论内容")
    target_type: CommentTargetType = Field(..., description="评论目标类型")
    target_id: str = Field(..., description="评论目标ID")
    parent_id: Optional[str] = Field(None, description="父评论ID，用于回复功能")


class CommentCreate(CommentBase):
    """创建评论请求模型"""
    pass


class CommentUpdate(BaseModel):
    """更新评论请求模型"""
    content: Optional[str] = Field(None, min_length=1, max_length=5000, description="评论内容")


class CommentAuthor(BaseModel):
    """评论作者信息模型"""
    id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    name: Optional[str] = Field(None, description="真实姓名")
    avatar: Optional[str] = Field(None, description="头像URL")
    
    class Config:
        from_attributes = True


class CommentResponse(CommentBase):
    """评论响应模型"""
    id: str = Field(..., description="评论ID")
    author_id: str = Field(..., description="评论作者ID")
    author: CommentAuthor = Field(..., description="评论作者信息")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    replies: List['CommentResponse'] = Field(default=[], description="回复列表")
    
    class Config:
        from_attributes = True


class CommentListResponse(BaseModel):
    """评论列表响应模型"""
    comments: List[CommentResponse] = Field(..., description="评论列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    size: int = Field(..., description="每页大小")
    pages: int = Field(..., description="总页数")


# 解决前向引用问题
CommentResponse.model_rebuild()